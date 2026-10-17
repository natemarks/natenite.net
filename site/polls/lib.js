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
  async function prepareSubmission(pollId, answers) {
    var body = JSON.stringify({ pollId: pollId, answers: answers });
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
        return typeof answer !== 'string' || answer === '';
      })
      .map(function (question) { return question.id; });
  }

  return {
    sha256Hex: sha256Hex,
    prepareSubmission: prepareSubmission,
    missingQuestions: missingQuestions
  };
});
