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
