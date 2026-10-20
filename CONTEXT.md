# Polls

Simple public web polls served at `polls.natenite.net/<poll-id>`. A respondent answers a poll's questions and may leave an email address. Only the site owner reads the data.

## Language

**Poll**:
A named set of questions with its own route, identified by a poll ID.
_Avoid_: Survey, form, questionnaire

**Poll definition**:
The authored description of a poll: its ID, title, questions, and optional closing time. Owned by the repository, not by respondents.
_Avoid_: Poll config, schema

**Question**:
One prompt in a poll, of a fixed kind: single choice, multiple choice, rating, or free text.
_Avoid_: Field, item

**Response**:
One respondent's complete submission to a poll, holding an answer for each question they answered.
_Avoid_: Submission, vote, entry

**Answer**:
The value a respondent gave to one question within a response.
_Avoid_: Value, result

**Email record**:
The optional email address a respondent left, kept apart from the response and linked to it by response ID. Held for the owner's manual use only.
_Avoid_: Contact, subscriber

**Browser token**:
A random identifier generated in a respondent's browser and stored (hashed) on each response, so repeat submissions from one browser can be recognised later. It is not an identity.
_Avoid_: Session, user ID, fingerprint

**Closing time**:
The optional moment after which a poll no longer accepts responses.
_Avoid_: Deadline, expiry
