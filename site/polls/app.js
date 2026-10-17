// Builds the poll form from the poll's definition and submits the answers.
// All text is set with textContent, never innerHTML. The request signing
// logic lives in lib.js (PollLib), which has its own tests.
(function () {
  'use strict';

  var root = document.getElementById('poll');

  function pollIdFromPath() {
    var parts = window.location.pathname.split('/').filter(Boolean);
    return parts.length ? parts[0] : '';
  }

  function showMessage(text) {
    root.textContent = '';
    var p = document.createElement('p');
    p.textContent = text;
    root.appendChild(p);
  }

  function renderSingleChoice(question) {
    var fieldset = document.createElement('fieldset');
    var legend = document.createElement('legend');
    legend.textContent = question.prompt;
    fieldset.appendChild(legend);

    question.options.forEach(function (option) {
      var label = document.createElement('label');
      var input = document.createElement('input');
      input.type = 'radio';
      input.name = question.id;
      input.value = option.id;
      label.appendChild(input);
      label.appendChild(document.createTextNode(' ' + option.label));
      fieldset.appendChild(label);
    });
    return fieldset;
  }

  function readAnswers(form, questions) {
    var answers = {};
    questions.forEach(function (question) {
      var value = form.elements.namedItem(question.id).value;
      if (value) {
        answers[question.id] = value;
      }
    });
    return answers;
  }

  function renderPoll(definition) {
    document.title = definition.title;
    root.textContent = '';

    var heading = document.createElement('h1');
    heading.textContent = definition.title;
    root.appendChild(heading);

    var questions = definition.questions.filter(function (question) {
      return question.type === 'single';
    });

    var form = document.createElement('form');
    questions.forEach(function (question) {
      form.appendChild(renderSingleChoice(question));
    });

    var button = document.createElement('button');
    button.type = 'submit';
    button.textContent = 'Submit';
    form.appendChild(button);

    var status = document.createElement('p');
    status.className = 'note';
    status.setAttribute('role', 'status');
    form.appendChild(status);

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var answers = readAnswers(form, questions);
      if (Object.keys(answers).length !== questions.length) {
        status.textContent = 'Please answer every question.';
        return;
      }
      button.disabled = true;
      status.textContent = 'Sending…';
      PollLib.prepareSubmission(definition.id, answers)
        .then(function (prepared) {
          return fetch('/submit', {
            method: 'POST',
            headers: prepared.headers,
            body: prepared.body
          });
        })
        .then(function (response) {
          if (response.status !== 201) {
            throw new Error('status ' + response.status);
          }
          showMessage('Thank you! Your response was recorded.');
        })
        .catch(function () {
          button.disabled = false;
          status.textContent =
            'Sorry, your response could not be sent. Please try again.';
        });
    });

    root.appendChild(form);
  }

  var pollId = pollIdFromPath();
  if (!/^[a-z0-9-]+$/.test(pollId)) {
    showMessage('Poll not found.');
    return;
  }

  fetch('/definitions/' + pollId + '.json')
    .then(function (response) {
      if (!response.ok) {
        throw new Error('not found');
      }
      return response.json();
    })
    .then(renderPoll)
    .catch(function () {
      showMessage('Poll not found.');
    });
})();
