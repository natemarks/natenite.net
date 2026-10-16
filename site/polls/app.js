// Builds the poll form from the poll's definition. Slice 02 only displays the
// form; submitting arrives in a later slice. All text is set with
// textContent, never innerHTML.
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

  function renderPoll(definition) {
    document.title = definition.title;
    root.textContent = '';

    var heading = document.createElement('h1');
    heading.textContent = definition.title;
    root.appendChild(heading);

    var form = document.createElement('form');
    definition.questions.forEach(function (question) {
      if (question.type === 'single') {
        form.appendChild(renderSingleChoice(question));
      }
    });

    var note = document.createElement('p');
    note.className = 'note';
    note.textContent = 'Submitting is not available yet.';
    form.appendChild(note);
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
