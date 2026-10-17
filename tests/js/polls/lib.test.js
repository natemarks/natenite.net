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
