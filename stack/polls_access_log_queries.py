"""Athena over the polls CloudFront access logs.

Purpose:
- Read the delivered JSON log files in place: a Glue table with partitions
  worked out from the date folders, so there is no crawler or repair step.
- Keep query results in their own expiring folder, in a workgroup that caps
  how much one query may scan.
- Save the routine questions as queries.
"""

import re
from collections import namedtuple

from aws_cdk import (
    aws_athena as athena,
    aws_glue as glue,
    aws_s3 as s3,
)
from constructs import Construct

LOG_PREFIX = "cloudfront/polls"
RESULTS_PREFIX = "athena-results"
TABLE = "cloudfront_logs"
# Every projected folder is listed in S3 when a query is planned, so keep the
# count small (about 370 a year). Extend the year range when it runs out.
SavedQuery = namedtuple("SavedQuery", ["sql", "console_days"])

PARTITIONS = [("year", "2026,2030", None), ("month", "1,12", 2),
              ("day", "1,31", 2)]  # fmt: skip

# The fields of a delivered log line, as the delivery names them.
LOG_FIELDS = [
    "date", "time", "x-edge-location", "sc-bytes", "c-ip", "cs-method",
    "cs(Host)", "cs-uri-stem", "sc-status", "cs(Referer)", "cs(User-Agent)",
    "cs-uri-query", "cs(Cookie)", "x-edge-result-type", "x-edge-request-id",
    "x-host-header", "cs-protocol", "cs-bytes", "time-taken",
    "x-forwarded-for", "ssl-protocol", "ssl-cipher",
    "x-edge-response-result-type", "cs-protocol-version", "fle-status",
    "fle-encrypted-fields", "c-port", "time-to-first-byte",
    "x-edge-detailed-result-type", "sc-content-type", "sc-content-len",
    "sc-range-start", "sc-range-end",
]  # fmt: skip

# Only the newest partitions are read, so a query stays small as logs grow.
_RECENT = (
    "year >= year(current_date - interval '{days}' day)\n"
    "  AND \"date\" >= cast(current_date - interval '{days}' day AS varchar)"
)

# The saved queries, with the day count and database left to fill in. The
# console copies use `console_days`; the owner script fills in its own window.
QUERIES = {
    "polls/errors-by-day": SavedQuery(
        'SELECT "date", sc_status, x_edge_result_type, count(*) AS requests\n'
        "FROM {database}.cloudfront_logs\n"
        "WHERE " + _RECENT + "\n"
        "  AND cast(sc_status AS integer) >= 400\n"
        "GROUP BY 1, 2, 3\n"
        "ORDER BY 1 DESC, 4 DESC",
        30,
    ),
    "polls/top-client-addresses": SavedQuery(
        "SELECT c_ip, count(*) AS requests,\n"
        "  count_if(sc_status = '403') AS blocked,\n"
        "  count_if(cast(sc_status AS integer) >= 400) AS rejected\n"
        "FROM {database}.cloudfront_logs\n"
        "WHERE " + _RECENT + "\n"
        "GROUP BY c_ip\n"
        "ORDER BY requests DESC\n"
        "LIMIT 20",
        7,
    ),
    "polls/blocked-and-throttled": SavedQuery(
        'SELECT "date", "time", sc_status, cs_method, cs_uri_stem,\n'
        "  x_edge_detailed_result_type, c_ip\n"
        "FROM {database}.cloudfront_logs\n"
        "WHERE " + _RECENT + "\n"
        "  AND sc_status IN ('403', '429')\n"
        'ORDER BY "date" DESC, "time" DESC\n'
        "LIMIT 100",
        7,
    ),
}


def database_name(prefix: str) -> str:
    """The Glue database holding the log table."""
    return f"{prefix.lower()}_access_logs"


def workgroup_name(prefix: str) -> str:
    """The Athena workgroup the queries run in."""
    return f"{prefix}-access-logs"


def render_query(name: str, database: str, days: int | None = None) -> str:
    """The saved query `name` as SQL, for `days` (default: the console's)."""
    query = QUERIES[name]
    return query.sql.format(
        database=database,
        days=days if days is not None else query.console_days,
    )


def column_name(field: str) -> str:
    """The Athena column for a log field: lowercase letters and underscores."""
    return re.sub(r"[^a-z0-9]+", "_", field.lower()).strip("_")


def _projection_parameters(location: str) -> dict:
    """Table parameters that work the partitions out from the folder names."""
    parameters = {"projection.enabled": "true"}
    for name, value_range, digits in PARTITIONS:
        parameters[f"projection.{name}.type"] = "integer"
        parameters[f"projection.{name}.range"] = value_range
        if digits:
            parameters[f"projection.{name}.digits"] = str(digits)
    parameters["storage.location.template"] = (
        location
        + "/".join(f"{name}=${{{name}}}" for name, _, _ in PARTITIONS)
        + "/"
    )
    return parameters


class AccessLogQueries(Construct):  # pylint: disable=too-few-public-methods
    """The table, workgroup and saved queries over the access logs."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket: s3.IBucket,
        prefix: str,
    ):
        super().__init__(scope, construct_id)
        db_name = database_name(prefix)
        database = glue.CfnDatabase(
            self,
            "Database",
            catalog_id=bucket.stack.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=db_name
            ),
        )
        location = f"s3://{bucket.bucket_name}/{LOG_PREFIX}/"
        parameters = _projection_parameters(location)
        table = glue.CfnTable(
            self,
            "Table",
            catalog_id=bucket.stack.account,
            database_name=db_name,
            table_input=glue.CfnTable.TableInputProperty(
                name=TABLE,
                table_type="EXTERNAL_TABLE",
                parameters=parameters,
                partition_keys=[
                    glue.CfnTable.ColumnProperty(name=name, type="int")
                    for name, _, _ in PARTITIONS
                ],
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    location=location,
                    columns=[
                        glue.CfnTable.ColumnProperty(
                            name=column_name(field), type="string"
                        )
                        for field in LOG_FIELDS
                    ],
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format=(
                        "org.apache.hadoop.hive.ql.io."
                        "HiveIgnoreKeyTextOutputFormat"
                    ),
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library="org.openx.data.jsonserde.JsonSerDe",
                        # Athena names can't hold - or (); map each back
                        parameters={
                            f"mapping.{column_name(field)}": field
                            for field in LOG_FIELDS
                        },
                    ),
                ),
            ),
        )
        table.add_dependency(database)
        workgroup = self._workgroup(bucket, prefix)
        for name in QUERIES:
            saved = athena.CfnNamedQuery(
                self,
                f"Query{name.split('/')[1].title().replace('-', '')}",
                name=name,
                database=db_name,
                work_group=workgroup.ref,
                query_string=render_query(name, db_name),
            )
            saved.add_dependency(table)

    def _workgroup(self, bucket: s3.IBucket, prefix: str):
        """The workgroup: results in the expiring folder, scans capped."""
        results = athena.CfnWorkGroup.ResultConfigurationProperty(
            output_location=f"s3://{bucket.bucket_name}/{RESULTS_PREFIX}/",
            encryption_configuration=(
                athena.CfnWorkGroup.EncryptionConfigurationProperty(
                    encryption_option="SSE_S3"
                )
            ),
        )
        settings = athena.CfnWorkGroup.WorkGroupConfigurationProperty(
            enforce_work_group_configuration=True,
            bytes_scanned_cutoff_per_query=1024**3,
            result_configuration=results,
        )
        return athena.CfnWorkGroup(
            self,
            "WorkGroup",
            name=workgroup_name(prefix),
            description="Queries over the polls CloudFront access logs",
            work_group_configuration=settings,
        )
