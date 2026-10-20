// Pure logic for the poll page, with no DOM access so it can be tested in
// Node. Loaded as a plain script in the browser (exposes `PollLib`) and with
// `require` in tests.
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.PollLib = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Hex-encoded SHA-256 of the UTF-8 bytes of `text`. CloudFront requires
  // this value in the x-amz-content-sha256 header of a POST to a Lambda
  // function URL, and it must be computed over exactly the bytes sent.
  async function sha256Hex(text) {
    var bytes = new TextEncoder().encode(text);
    var digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest))
      .map(function (b) { return b.toString(16).padStart(2, '0'); })
      .join('');
  }

  // The request body and the headers to send with it. The body string is
  // built once and hashed as-is, so the signed bytes are the sent bytes.
  async function prepareSubmission(pollId, answers, email, browserToken) {
    var request = { pollId: pollId, answers: answers };
    var trimmed = typeof email === 'string' ? email.trim() : '';
    if (trimmed !== '') {
      request.email = trimmed;
    }
    if (typeof browserToken === 'string' && browserToken !== '') {
      request.browserToken = browserToken;
    }
    var body = JSON.stringify(request);
    return {
      body: body,
      headers: {
        'content-type': 'application/json',
        'x-amz-content-sha256': await sha256Hex(body)
      }
    };
  }

  // IDs of the questions that have no answer yet. A multiple-choice question
  // needs at least one selection; a rating of 0 is a real answer.
  function missingQuestions(questions, answers) {
    return questions
      .filter(function (question) {
        var answer = answers[question.id];
        if (question.type === 'multi') {
          return !Array.isArray(answer) || answer.length === 0;
        }
        if (question.type === 'rating') {
          return typeof answer !== 'number';
        }
        if (question.type === 'text') {
          return typeof answer !== 'string' || answer.trim() === '';
        }
        return typeof answer !== 'string' || answer === '';
      })
      .map(function (question) { return question.id; });
  }

  // The free-text limit, in Unicode characters. The submit function keeps the
  // authoritative copy; a unit test fails if the two numbers differ.
  var MAX_TEXT_CHARS = 500;

  // Characters as the server counts them (code points), not UTF-16 units:
  // an emoji is two units in JavaScript but one character.
  function textLength(text) {
    return Array.from(text).length;
  }

  function charactersLeft(text) {
    return MAX_TEXT_CHARS - textLength(text);
  }

  // IDs of the text questions whose answer is longer than the limit.
  function overLimitQuestions(questions, answers) {
    return questions
      .filter(function (question) {
        var answer = answers[question.id];
        return question.type === 'text' &&
          typeof answer === 'string' &&
          textLength(answer) > MAX_TEXT_CHARS;
      })
      .map(function (question) { return question.id; });
  }

  // True when the poll has a closing time that has passed. `nowMs` is passed
  // in so the clock can be controlled in tests. This only chooses what the
  // page shows: the server decides whether a submission is accepted.
  function isClosed(definition, nowMs) {
    if (!definition.closesAt) {
      return false;
    }
    var closing = Date.parse(definition.closesAt);
    return !Number.isNaN(closing) && nowMs >= closing;
  }

  // A message for rejections the respondent can act on, or null when the
  // page should show its generic failure message instead.
  var REJECTION_MESSAGES = {
    invalid_email: 'Please check your email address.',
    email_too_long: 'Your email address is too long.',
    // The answers are stored; only the address was not.
    email_not_stored:
      'Thank you! Your answers were saved, but we could not save your ' +
      'email address.'
  };

  function rejectionMessage(reason) {
    return Object.prototype.hasOwnProperty.call(REJECTION_MESSAGES, reason)
      ? REJECTION_MESSAGES[reason]
      : null;
  }

  // A random label for this browser: 128 random bits as 32 hex characters.
  // It identifies no one. `fill` fills a Uint8Array with random bytes
  // (crypto.getRandomValues in the browser); it is passed in for tests.
  function newBrowserToken(fill) {
    var bytes = fill(new Uint8Array(16));
    return Array.from(bytes)
      .map(function (b) { return b.toString(16).padStart(2, '0'); })
      .join('');
  }

  var TOKEN_KEY = 'poll-browser-token';
  var TOKEN_SHAPE = /^[0-9a-f]{32}$/;

  // This browser's token: the stored one, or a new one that is stored. If
  // storage is blocked the token lasts only for this page view, so repeats
  // cannot be recognised, but nothing breaks.
  function getBrowserToken(storage, fill) {
    try {
      var stored = storage.getItem(TOKEN_KEY);
      if (typeof stored === 'string' && TOKEN_SHAPE.test(stored)) {
        return stored;
      }
    } catch (error) {
      return newBrowserToken(fill);
    }
    var token = newBrowserToken(fill);
    try {
      storage.setItem(TOKEN_KEY, token);
    } catch (error) {
      // Not persisted; still usable for this visit.
    }
    return token;
  }

  function answeredKey(pollId) {
    return 'poll-answered:' + pollId;
  }

  // Remember (per poll) that this browser has submitted, and when.
  function rememberSubmission(storage, pollId, nowMs) {
    try {
      storage.setItem(answeredKey(pollId), new Date(nowMs).toISOString());
    } catch (error) {
      // Storage blocked: the page just will not remember. Nothing breaks.
    }
  }

  // The ISO time of an earlier submission from this browser, or null.
  function previousSubmission(storage, pollId) {
    try {
      var stored = storage.getItem(answeredKey(pollId));
      if (typeof stored === 'string' && !Number.isNaN(Date.parse(stored))) {
        return stored;
      }
    } catch (error) {
      // Storage blocked.
    }
    return null;
  }

  // Informational only: it never stops anyone answering, because a browser
  // can be shared.
  function answeredNotice(isoTime) {
    return 'You already answered this poll in this browser on ' +
      isoTime.slice(0, 10) + '. ' +
      'If someone else is using this browser, you can answer too.';
  }

  // Whether a failed attempt is worth repeating after a short wait. An outcome
  // is { status, reason } from the server, or { networkError: true } when no
  // answer came back at all.
  function isRetryable(outcome) {
    if (outcome.networkError) {
      return true;
    }
    if (outcome.status === 429) {
      return true;
    }
    // The answers are already saved when only the email was lost; retrying
    // would store the response a second time.
    return outcome.status >= 500 && outcome.reason !== 'email_not_stored';
  }

  // Retries made after the first attempt: at most this many.
  var MAX_RETRIES = 3;

  // Milliseconds to wait before retry number `retryNumber` (1, 2, 3...):
  // 1s, 2s, 4s, each spread by up to 25% either way (jitter) so visitors
  // who hit a limit together do not all retry together. `random` returns a
  // number in [0, 1); it is passed in for tests.
  function retryDelayMs(retryNumber, random) {
    var base = 1000 * Math.pow(2, retryNumber - 1);
    return Math.round(base * (0.75 + 0.5 * random()));
  }

  // Try `send` (which resolves to an outcome, or rejects if the request
  // failed outright), repeating after a wait while the failure is worth
  // repeating, up to MAX_RETRIES times. `sleep(ms)` and `random` are passed in
  // for tests; `onRetry(retryNumber, delayMs)` is called before each wait so
  // the page can say what it is doing.
  async function sendWithRetries(send, sleep, random, onRetry) {
    var attempts = 0;
    for (;;) {
      attempts += 1;
      var outcome;
      try {
        outcome = await send();
      } catch (error) {
        outcome = { networkError: true };
      }
      var retries = attempts - 1;
      if (!isRetryable(outcome) || retries >= MAX_RETRIES) {
        return { outcome: outcome, attempts: attempts };
      }
      var delay = retryDelayMs(retries + 1, random);
      if (onRetry) {
        onRetry(retries + 1, delay);
      }
      await sleep(delay);
    }
  }

  // Whether to tell the respondent the poll is busy. That covers failures
  // worth repeating plus a 403, which only the edge returns (a WAF
  // rate-limit block). A response where only the email was lost is not busy:
  // the answers were saved.
  function isBusy(outcome) {
    if (outcome.status === 500 && outcome.reason === 'email_not_stored') {
      return false;
    }
    return isRetryable(outcome) || outcome.status === 403;
  }

  var BUSY_MESSAGE =
    'The poll is busy right now. Your answers are still here. ' +
    'Please try again in a minute.';

  // The status and (when the body is JSON with a text reason) the reason of
  // a fetch response. The edge answers with HTML when it blocks a request.
  async function describeResponse(response) {
    var outcome = { status: response.status };
    try {
      var data = await response.json();
      if (data && typeof data.reason === 'string') {
        outcome.reason = data.reason;
      }
    } catch (error) {
      // Not JSON: the status alone is the outcome.
    }
    return outcome;
  }

  return {
    describeResponse: describeResponse,
    BUSY_MESSAGE: BUSY_MESSAGE,
    isBusy: isBusy,
    sendWithRetries: sendWithRetries,
    MAX_RETRIES: MAX_RETRIES,
    retryDelayMs: retryDelayMs,
    isRetryable: isRetryable,
    rememberSubmission: rememberSubmission,
    previousSubmission: previousSubmission,
    answeredNotice: answeredNotice,
    getBrowserToken: getBrowserToken,
    newBrowserToken: newBrowserToken,
    rejectionMessage: rejectionMessage,
    MAX_TEXT_CHARS: MAX_TEXT_CHARS,
    isClosed: isClosed,
    overLimitQuestions: overLimitQuestions,
    textLength: textLength,
    charactersLeft: charactersLeft,
    sha256Hex: sha256Hex,
    prepareSubmission: prepareSubmission,
    missingQuestions: missingQuestions
  };
});
