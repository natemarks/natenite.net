// Builds the poll form from the poll's definition and submits the answers.
// All text is set with textContent, never innerHTML. The request signing
// logic lives in lib.js (PollLib), which has its own tests.
(function () {
  'use strict';

  var root = document.getElementById('poll');

  // Even reading window.localStorage can throw (storage blocked); the
  // library tolerates a storage whose methods throw.
  function browserStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return {
        getItem: function () { throw error; },
        setItem: function () { throw error; }
      };
    }
  }

  function randomBytes(bytes) {
    return window.crypto.getRandomValues(bytes);
  }

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

  function renderChoices(question, inputType, options) {
    var fieldset = document.createElement('fieldset');
    var legend = document.createElement('legend');
    legend.textContent = question.prompt;
    fieldset.appendChild(legend);

    options.forEach(function (option) {
      var label = document.createElement('label');
      var input = document.createElement('input');
      input.type = inputType;
      input.name = question.id;
      input.value = option.id;
      label.appendChild(input);
      label.appendChild(document.createTextNode(' ' + option.label));
      fieldset.appendChild(label);
    });
    return fieldset;
  }

  function ratingOptions(question) {
    var options = [];
    for (var n = question.min; n <= question.max; n += 1) {
      options.push({ id: String(n), label: String(n) });
    }
    return options;
  }

  function counterText(left) {
    return left >= 0
      ? left + ' characters left'
      : -left + ' characters over the limit';
  }

  function renderText(question) {
    var fieldset = document.createElement('fieldset');
    var legend = document.createElement('legend');
    legend.textContent = question.prompt;
    fieldset.appendChild(legend);

    var textarea = document.createElement('textarea');
    textarea.name = question.id;
    textarea.rows = 4;
    var counter = document.createElement('p');
    counter.className = 'note';
    counter.id = 'count-' + question.id;
    counter.setAttribute('aria-live', 'polite');
    textarea.setAttribute('aria-describedby', counter.id);

    function update() {
      var left = PollLib.charactersLeft(textarea.value);
      counter.textContent = counterText(left);
      counter.classList.toggle('over', left < 0);
    }
    textarea.addEventListener('input', update);
    update();

    fieldset.appendChild(textarea);
    fieldset.appendChild(counter);
    return fieldset;
  }

  function renderQuestion(question) {
    if (question.type === 'text') {
      return renderText(question);
    }
    if (question.type === 'multi') {
      return renderChoices(question, 'checkbox', question.options);
    }
    if (question.type === 'rating') {
      return renderChoices(question, 'radio', ratingOptions(question));
    }
    return renderChoices(question, 'radio', question.options);
  }

  // Answers in the shapes the server expects: an option ID, a list of
  // option IDs, or an integer rating. Unanswered questions are left out.
  function readAnswers(form, questions) {
    var answers = {};
    questions.forEach(function (question) {
      var checked = Array.prototype.filter.call(form.elements, function (el) {
        return el.name === question.id && el.checked;
      });
      if (question.type === 'text') {
        answers[question.id] = form.elements.namedItem(question.id).value;
      } else if (question.type === 'multi') {
        answers[question.id] = checked.map(function (el) { return el.value; });
      } else if (checked.length) {
        answers[question.id] = question.type === 'rating'
          ? Number(checked[0].value)
          : checked[0].value;
      }
    });
    return answers;
  }

  function renderPoll(definition) {
    document.title = definition.title;
    root.textContent = '';

    // The visitor's clock only decides what to show; the server enforces it.
    if (PollLib.isClosed(definition, Date.now())) {
      showMessage('This poll is closed.');
      return;
    }

    var heading = document.createElement('h1');
    heading.textContent = definition.title;
    root.appendChild(heading);

    var questions = definition.questions.filter(function (question) {
      return ['single', 'multi', 'rating', 'text'].indexOf(question.type) !== -1;
    });

    var earlier = PollLib.previousSubmission(browserStorage(), definition.id);
    if (earlier) {
      // Informational only: the form stays usable (a browser can be shared).
      var earlierNote = document.createElement('p');
      earlierNote.className = 'note';
      earlierNote.setAttribute('role', 'status');
      earlierNote.textContent = PollLib.answeredNotice(earlier);
      root.appendChild(earlierNote);
    }

    var form = document.createElement('form');
    questions.forEach(function (question) {
      form.appendChild(renderQuestion(question));
    });

    // Named "respondent-email" so it can never collide with a question ID
    // (question IDs cannot contain hyphens).
    var emailBox = document.createElement('p');
    var emailLabel = document.createElement('label');
    emailLabel.htmlFor = 'respondent-email';
    emailLabel.textContent = 'Email (optional)';
    var emailInput = document.createElement('input');
    emailInput.type = 'email';
    emailInput.id = 'respondent-email';
    emailInput.name = 'respondent-email';
    emailInput.autocomplete = 'email';
    emailInput.setAttribute('aria-describedby', 'email-notice');
    var emailNotice = document.createElement('span');
    emailNotice.id = 'email-notice';
    emailNotice.className = 'note';
    emailNotice.textContent =
      ' Optional. We keep your address until you ask us to remove it.';
    emailBox.appendChild(emailLabel);
    emailBox.appendChild(document.createElement('br'));
    emailBox.appendChild(emailInput);
    emailBox.appendChild(emailNotice);
    form.appendChild(emailBox);

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
      if (PollLib.missingQuestions(questions, answers).length) {
        status.textContent = 'Please answer every question.';
        return;
      }
      if (PollLib.overLimitQuestions(questions, answers).length) {
        status.textContent = 'Please shorten your answer: the limit is ' +
          PollLib.MAX_TEXT_CHARS + ' characters.';
        return;
      }
      button.disabled = true;
      status.textContent = 'Sending…';
      PollLib.prepareSubmission(
        definition.id,
        answers,
        emailInput.value,
        PollLib.getBrowserToken(browserStorage(), randomBytes)
      )
        .then(function (prepared) {
          return fetch('/submit', {
            method: 'POST',
            headers: prepared.headers,
            body: prepared.body
          });
        })
        .then(function (response) {
          if (response.status === 410) {
            showMessage('This poll is closed.');
            return;
          }
          if (response.status === 201) {
            PollLib.rememberSubmission(
              browserStorage(), definition.id, Date.now()
            );
            showMessage('Thank you! Your response was recorded.');
            return null;
          }
          return response.json().catch(function () {
            return {};
          }).then(function (data) {
            var message = PollLib.rejectionMessage(data.reason);
            if (data.reason === 'email_not_stored') {
              // The answers are saved: do not invite a duplicate resubmit.
              PollLib.rememberSubmission(
                browserStorage(), definition.id, Date.now()
              );
              showMessage(message);
              return;
            }
            var error = new Error('status ' + response.status);
            error.userMessage = message;
            throw error;
          });
        })
        .catch(function (error) {
          button.disabled = false;
          status.textContent = (error && error.userMessage) ||
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
