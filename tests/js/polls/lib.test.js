// Tests for the poll page's pure logic (no DOM). Run: node --test "tests/js/**/*.test.js"
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const lib = require('../../../site/polls/lib.js');

test('sha256Hex matches published SHA-256 vectors', async () => {
  // NIST / RFC 6234 vectors for "abc" and the empty string.
  assert.equal(
    await lib.sha256Hex('abc'),
    'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
  );
  assert.equal(
    await lib.sha256Hex(''),
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  );
});

test('sha256Hex hashes the UTF-8 bytes of non-ASCII text', async () => {
  // Expected value computed independently with Python hashlib.
  assert.equal(
    await lib.sha256Hex('café ☕'),
    'a7e46d54289812af2aa5b08c2fbab5d24bccfc6586df55b187272c8a2a31c85f'
  );
});

test('prepareSubmission signs exactly the body it returns', async () => {
  const { body, headers } = await lib.prepareSubmission('poll1', { q1: 'a' });

  assert.equal(body, '{"pollId":"poll1","answers":{"q1":"a"}}');
  assert.deepEqual(headers, {
    'content-type': 'application/json',
    // Expected value computed independently with Python hashlib.
    'x-amz-content-sha256':
      '30e7364294346df8490dc572520d65764a4640f19829b0dc0ffa2ee23bf7b082',
  });
});

const QUESTIONS = [
  { id: 'q1', type: 'single' },
  { id: 'q2', type: 'multi' },
  { id: 'q3', type: 'rating', min: 0, max: 5 }
];

test('missingQuestions is empty when every question is answered', () => {
  assert.deepEqual(
    lib.missingQuestions(QUESTIONS, { q1: 'a', q2: ['x'], q3: 4 }),
    []
  );
});

test('missingQuestions names each unanswered question', () => {
  assert.deepEqual(lib.missingQuestions(QUESTIONS, {}), ['q1', 'q2', 'q3']);
  assert.deepEqual(
    lib.missingQuestions(QUESTIONS, { q1: 'a', q3: 2 }),
    ['q2']
  );
});

test('an empty multiple-choice selection counts as unanswered', () => {
  assert.deepEqual(
    lib.missingQuestions(QUESTIONS, { q1: 'a', q2: [], q3: 2 }),
    ['q2']
  );
});

test('a rating of zero is an answer, not a missing one', () => {
  assert.deepEqual(
    lib.missingQuestions(QUESTIONS, { q1: 'a', q2: ['x'], q3: 0 }),
    []
  );
});

test('textLength counts Unicode characters, as the server does', () => {
  assert.equal(lib.textLength('abc'), 3);
  assert.equal(lib.textLength('café'), 4);
  // Outside the BMP: two UTF-16 units in JavaScript, one character.
  assert.equal('😀'.length, 2);
  assert.equal(lib.textLength('😀😀'), 2);
  assert.equal(lib.textLength(''), 0);
});

test('charactersLeft counts down from the 500 character limit', () => {
  assert.equal(lib.charactersLeft(''), 500);
  assert.equal(lib.charactersLeft('abc'), 497);
  assert.equal(lib.charactersLeft('x'.repeat(500)), 0);
  assert.equal(lib.charactersLeft('x'.repeat(501)), -1);
  assert.equal(lib.charactersLeft('😀'.repeat(500)), 0);
});

const TEXT_QUESTIONS = [{ id: 'q4', type: 'text' }];

test('a blank or whitespace-only text answer counts as unanswered', () => {
  assert.deepEqual(lib.missingQuestions(TEXT_QUESTIONS, {}), ['q4']);
  assert.deepEqual(lib.missingQuestions(TEXT_QUESTIONS, { q4: '' }), ['q4']);
  assert.deepEqual(lib.missingQuestions(TEXT_QUESTIONS, { q4: ' \n\t ' }), ['q4']);
  assert.deepEqual(lib.missingQuestions(TEXT_QUESTIONS, { q4: ' hi ' }), []);
});

test('overLimitQuestions names text answers longer than the limit', () => {
  const questions = [
    { id: 'q1', type: 'single' },
    { id: 'q4', type: 'text' },
    { id: 'q5', type: 'text' }
  ];

  assert.deepEqual(
    lib.overLimitQuestions(questions, { q1: 'a', q4: 'x'.repeat(500) }),
    []
  );
  assert.deepEqual(
    lib.overLimitQuestions(questions, { q4: 'x'.repeat(501), q5: 'ok' }),
    ['q4']
  );
  // 500 emoji are 1000 UTF-16 units but only 500 characters: within the limit.
  assert.deepEqual(lib.overLimitQuestions(questions, { q5: '😀'.repeat(500) }), []);
  assert.deepEqual(lib.overLimitQuestions(questions, { q5: '😀'.repeat(501) }), ['q5']);
});

const CLOSING = '2026-10-16T12:00:00Z';
const CLOSING_MS = Date.parse(CLOSING);

test('isClosed is true from the closing instant on, using the given time', () => {
  const poll = { id: 'p', closesAt: CLOSING };

  assert.equal(lib.isClosed(poll, CLOSING_MS - 1000), false);
  assert.equal(lib.isClosed(poll, CLOSING_MS), true);
  assert.equal(lib.isClosed(poll, CLOSING_MS + 1000), true);
});

test('a poll without a closing time never counts as closed', () => {
  assert.equal(lib.isClosed({ id: 'p' }, CLOSING_MS * 2), false);
});

test('an unreadable closing time is left to the server to enforce', () => {
  assert.equal(lib.isClosed({ id: 'p', closesAt: 'soon' }, CLOSING_MS), false);
});

test('prepareSubmission adds a trimmed email and signs that exact body', async () => {
  const { body, headers } = await lib.prepareSubmission(
    'poll1', { q1: 'a' }, '  reader@example.com  '
  );

  assert.equal(
    body,
    '{"pollId":"poll1","answers":{"q1":"a"},"email":"reader@example.com"}'
  );
  // Expected value computed independently with Python hashlib.
  assert.equal(
    headers['x-amz-content-sha256'],
    '244e8f34a554f1f6f0d190e918868b826935891ca2a7d086ae7e0d3bc21643db'
  );
});

test('a blank or missing email is left out of the request', async () => {
  const plain = await lib.prepareSubmission('poll1', { q1: 'a' });

  for (const blank of [undefined, null, '', '   ', '\n\t']) {
    const prepared = await lib.prepareSubmission('poll1', { q1: 'a' }, blank);
    assert.equal(prepared.body, plain.body);
    assert.deepEqual(prepared.headers, plain.headers);
  }
});

test('rejectionMessage explains email problems and leaves others generic', () => {
  assert.equal(
    lib.rejectionMessage('invalid_email'),
    'Please check your email address.'
  );
  assert.equal(
    lib.rejectionMessage('email_too_long'),
    'Your email address is too long.'
  );
  assert.equal(lib.rejectionMessage('unknown_option'), null);
  assert.equal(lib.rejectionMessage(undefined), null);
});

test('rejectionMessage tells the respondent when only the email was lost', () => {
  assert.equal(
    lib.rejectionMessage('email_not_stored'),
    'Thank you! Your answers were saved, but we could not save your email address.'
  );
});

// An in-memory stand-in for localStorage, optionally broken like a
// browser with storage blocked.
function fakeStorage(broken) {
  const data = new Map();
  return {
    data,
    getItem(key) {
      if (broken) { throw new Error('storage blocked'); }
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      if (broken) { throw new Error('storage blocked'); }
      data.set(key, String(value));
    }
  };
}

// A random source that fills the array with a known sequence.
function sequenceRandom(start) {
  let next = start;
  return (bytes) => {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = next % 256;
      next += 1;
    }
    return bytes;
  };
}

test('newBrowserToken is 32 lower-case hex characters from 16 random bytes', () => {
  assert.equal(
    lib.newBrowserToken(sequenceRandom(0)),
    '000102030405060708090a0b0c0d0e0f'
  );
  assert.equal(
    lib.newBrowserToken(sequenceRandom(250)),
    'fafbfcfdfeff00010203040506070809'
  );
  assert.match(lib.newBrowserToken(sequenceRandom(7)), /^[0-9a-f]{32}$/);
});

test('getBrowserToken makes a token on the first visit and keeps it', () => {
  const storage = fakeStorage(false);

  const first = lib.getBrowserToken(storage, sequenceRandom(0));
  assert.equal(first, '000102030405060708090a0b0c0d0e0f');
  assert.equal(storage.data.get('poll-browser-token'), first);

  // A later visit gets the same token and does not use the random source.
  const later = lib.getBrowserToken(storage, () => {
    throw new Error('should not be called');
  });
  assert.equal(later, first);
});

test('a stored value that is not a token is replaced', () => {
  const storage = fakeStorage(false);
  storage.data.set('poll-browser-token', 'not-a-token');

  const token = lib.getBrowserToken(storage, sequenceRandom(16));

  assert.equal(token, '101112131415161718191a1b1c1d1e1f');
  assert.equal(storage.data.get('poll-browser-token'), token);
});

test('with storage blocked a token is still made, for this visit only', () => {
  const storage = fakeStorage(true);

  const token = lib.getBrowserToken(storage, sequenceRandom(0));

  assert.match(token, /^[0-9a-f]{32}$/);
});

const SUBMITTED_MS = Date.parse('2026-10-17T12:00:00Z');

test('a submitted poll is remembered per poll, with the time', () => {
  const storage = fakeStorage(false);

  assert.equal(lib.previousSubmission(storage, 'poll1'), null);

  lib.rememberSubmission(storage, 'poll1', SUBMITTED_MS);

  assert.equal(
    lib.previousSubmission(storage, 'poll1'),
    '2026-10-17T12:00:00.000Z'
  );
  assert.equal(lib.previousSubmission(storage, 'poll2'), null);
});

test('a stored value that is not a time is ignored', () => {
  const storage = fakeStorage(false);
  storage.data.set('poll-answered:poll1', 'yesterday-ish');

  assert.equal(lib.previousSubmission(storage, 'poll1'), null);
});

test('with storage blocked nothing is remembered and nothing breaks', () => {
  const storage = fakeStorage(true);

  assert.doesNotThrow(() => lib.rememberSubmission(storage, 'poll1', SUBMITTED_MS));
  assert.equal(lib.previousSubmission(storage, 'poll1'), null);
});

test('the already-answered note names the date and does not block anyone', () => {
  assert.equal(
    lib.answeredNotice('2026-10-17T12:00:00.000Z'),
    'You already answered this poll in this browser on 2026-10-17. ' +
      'If someone else is using this browser, you can answer too.'
  );
});

const A_TOKEN = '000102030405060708090a0b0c0d0e0f';

test('prepareSubmission sends the browser token and signs that exact body', async () => {
  const withoutEmail = await lib.prepareSubmission('poll1', { q1: 'a' }, '', A_TOKEN);
  assert.equal(
    withoutEmail.body,
    '{"pollId":"poll1","answers":{"q1":"a"},"browserToken":"' + A_TOKEN + '"}'
  );
  // Expected values computed independently with Python hashlib.
  assert.equal(
    withoutEmail.headers['x-amz-content-sha256'],
    '0f510a8c3fa3b9991761aab7652138453015598fc11adba97d4a3a8eca5b218e'
  );

  const withEmail = await lib.prepareSubmission(
    'poll1', { q1: 'a' }, 'reader@example.com', A_TOKEN
  );
  assert.equal(
    withEmail.body,
    '{"pollId":"poll1","answers":{"q1":"a"},"email":"reader@example.com",' +
      '"browserToken":"' + A_TOKEN + '"}'
  );
  assert.equal(
    withEmail.headers['x-amz-content-sha256'],
    'c61fbfc77ea1a5075aa30d8ce091e2732a65d3783dec06d52f460ee75b405b8f'
  );
});

test('no token means none is sent', async () => {
  const plain = await lib.prepareSubmission('poll1', { q1: 'a' });
  for (const none of [undefined, null, '']) {
    const prepared = await lib.prepareSubmission('poll1', { q1: 'a' }, undefined, none);
    assert.equal(prepared.body, plain.body);
  }
});

test('isRetryable: transient failures are retried, everything else is not', () => {
  const retried = [
    { status: 429 },
    { status: 500 },
    { status: 502 },
    { status: 503 },
    { status: 504 },
    { networkError: true }
  ];
  for (const outcome of retried) {
    assert.equal(lib.isRetryable(outcome), true, JSON.stringify(outcome));
  }

  const notRetried = [
    { status: 201 },
    { status: 400, reason: 'unknown_option' },
    { status: 400, reason: 'invalid_email' },
    { status: 400, reason: 'answer_too_long' },
    // Only the edge returns 403 (a WAF block or a signing failure): waiting
    // seconds will not lift a rate-limit window, so it is not retried.
    { status: 403 },
    { status: 404, reason: 'unknown_poll' },
    { status: 405 },
    { status: 410, reason: 'poll_closed' },
    { status: 413, reason: 'payload_too_large' }
  ];
  for (const outcome of notRetried) {
    assert.equal(lib.isRetryable(outcome), false, JSON.stringify(outcome));
  }
});

test('a 500 saying only the email was lost is never retried', () => {
  // The answers are already saved: a retry would store a duplicate.
  assert.equal(
    lib.isRetryable({ status: 500, reason: 'email_not_stored' }),
    false
  );
});

test('retryDelayMs doubles each retry, starting at about a second', () => {
  const middle = () => 0.5;  // jitter factor exactly 1
  assert.equal(lib.retryDelayMs(1, middle), 1000);
  assert.equal(lib.retryDelayMs(2, middle), 2000);
  assert.equal(lib.retryDelayMs(3, middle), 4000);
});

test('retryDelayMs spreads each wait by up to 25 percent either way', () => {
  const lowest = () => 0;
  const highest = () => 0.999999;
  assert.equal(lib.retryDelayMs(1, lowest), 750);
  assert.equal(lib.retryDelayMs(2, lowest), 1500);
  assert.equal(lib.retryDelayMs(3, lowest), 3000);
  assert.equal(lib.retryDelayMs(1, highest), 1250);
  assert.equal(lib.retryDelayMs(2, highest), 2500);
  assert.equal(lib.retryDelayMs(3, highest), 5000);
});

// A send function that answers from a script (an Error means the request
// failed outright), and a sleep that records the waits without waiting.
function scripted(outcomes) {
  const calls = { count: 0 };
  const send = async () => {
    const next = outcomes[Math.min(calls.count, outcomes.length - 1)];
    calls.count += 1;
    if (next instanceof Error) { throw next; }
    return next;
  };
  return { send, calls };
}

function recordingSleep() {
  const delays = [];
  return { delays, sleep: async (ms) => { delays.push(ms); } };
}

const MIDDLE = () => 0.5;

test('sendWithRetries: a first-try success makes one attempt and never waits', async () => {
  const { send } = scripted([{ status: 201 }]);
  const { sleep, delays } = recordingSleep();

  const result = await lib.sendWithRetries(send, sleep, MIDDLE);

  assert.deepEqual(result, { outcome: { status: 201 }, attempts: 1 });
  assert.deepEqual(delays, []);
});

test('sendWithRetries recovers after a throttled attempt', async () => {
  const { send } = scripted([{ status: 429 }, { status: 201 }]);
  const { sleep, delays } = recordingSleep();

  const result = await lib.sendWithRetries(send, sleep, MIDDLE);

  assert.deepEqual(result, { outcome: { status: 201 }, attempts: 2 });
  assert.deepEqual(delays, [1000]);
});

test('sendWithRetries gives up after three retries, waiting 1s, 2s, 4s', async () => {
  const { send, calls } = scripted([{ status: 503 }]);
  const { sleep, delays } = recordingSleep();

  const result = await lib.sendWithRetries(send, sleep, MIDDLE);

  assert.deepEqual(result, { outcome: { status: 503 }, attempts: 4 });
  assert.equal(calls.count, 4);
  assert.deepEqual(delays, [1000, 2000, 4000]);
});

test('sendWithRetries stops at once for errors a retry cannot fix', async () => {
  for (const outcome of [
    { status: 400, reason: 'unknown_option' },
    { status: 403 },
    { status: 410, reason: 'poll_closed' },
    { status: 500, reason: 'email_not_stored' }
  ]) {
    const { send, calls } = scripted([outcome]);
    const { sleep, delays } = recordingSleep();

    const result = await lib.sendWithRetries(send, sleep, MIDDLE);

    assert.deepEqual(result, { outcome, attempts: 1 }, JSON.stringify(outcome));
    assert.equal(calls.count, 1);
    assert.deepEqual(delays, []);
  }
});

test('sendWithRetries treats a failed request as a network error and retries', async () => {
  const { send } = scripted([new Error('offline'), { status: 201 }]);
  const { sleep, delays } = recordingSleep();

  const recovered = await lib.sendWithRetries(send, sleep, MIDDLE);
  assert.deepEqual(recovered, { outcome: { status: 201 }, attempts: 2 });
  assert.deepEqual(delays, [1000]);

  const stuck = scripted([new Error('offline')]);
  const result = await lib.sendWithRetries(stuck.send, recordingSleep().sleep, MIDDLE);
  assert.deepEqual(result, { outcome: { networkError: true }, attempts: 4 });
});

test('sendWithRetries tells the page about each wait before it happens', async () => {
  const { send } = scripted([{ status: 429 }, { status: 429 }, { status: 201 }]);
  const { sleep } = recordingSleep();
  const waits = [];

  await lib.sendWithRetries(send, sleep, MIDDLE, (retryNumber, delayMs) => {
    waits.push([retryNumber, delayMs]);
  });

  assert.deepEqual(waits, [[1, 1000], [2, 2000]]);
});

test('isBusy covers throttling, server errors, network failures and edge blocks', () => {
  for (const outcome of [
    { status: 429 }, { status: 500 }, { status: 503 }, { status: 504 },
    { networkError: true },
    { status: 403 }  // a WAF rate-limit block (or a signing failure)
  ]) {
    assert.equal(lib.isBusy(outcome), true, JSON.stringify(outcome));
  }
  for (const outcome of [
    { status: 201 },
    { status: 400, reason: 'invalid_email' },
    { status: 404 }, { status: 410, reason: 'poll_closed' },
    { status: 500, reason: 'email_not_stored' }  // saved: not "busy"
  ]) {
    assert.equal(lib.isBusy(outcome), false, JSON.stringify(outcome));
  }
});

test('the busy message says answers are kept and when to try again', () => {
  assert.equal(
    lib.BUSY_MESSAGE,
    'The poll is busy right now. Your answers are still here. ' +
      'Please try again in a minute.'
  );
});

test('describeResponse reads the status and the reason when there is one', async () => {
  const reply = (status, body) => ({ status, json: async () => body });

  assert.deepEqual(
    await lib.describeResponse(reply(201, { responseId: 'X' })),
    { status: 201 }
  );
  assert.deepEqual(
    await lib.describeResponse(reply(400, { reason: 'invalid_email' })),
    { status: 400, reason: 'invalid_email' }
  );
  // The edge answers with HTML, not JSON, when it blocks a request.
  const html = { status: 403, json: async () => { throw new SyntaxError('not json'); } };
  assert.deepEqual(await lib.describeResponse(html), { status: 403 });
  // A reason that is not a string is ignored.
  assert.deepEqual(
    await lib.describeResponse(reply(500, { reason: { nested: true } })),
    { status: 500 }
  );
});
