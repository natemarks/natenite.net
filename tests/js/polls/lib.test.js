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
