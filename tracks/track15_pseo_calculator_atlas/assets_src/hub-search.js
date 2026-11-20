/**
 * Instant client-side search & cluster filter for Atlas Hub & Cluster Directory pages.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var searchInput = document.getElementById('atlas-search');
    var pills = document.querySelectorAll('[data-filter-cluster]');
    var cards = document.querySelectorAll('[data-dir-card]');
    var counter = document.getElementById('atlas-result-count');
    if (!cards.length) return;

    var activeCluster = 'all';

    function applyFilter() {
      var q = searchInput ? searchInput.value.trim().toLowerCase() : '';
      var visible = 0;
      for (var i = 0; i < cards.length; i += 1) {
        var card = cards[i];
        var cluster = card.getAttribute('data-cluster') || '';
        var haystack = (card.getAttribute('data-search') || '').toLowerCase();
        var matchCluster = (activeCluster === 'all') || (cluster === activeCluster);
        var matchText = (!q) || (haystack.indexOf(q) !== -1);
        if (matchCluster && matchText) {
          card.style.display = '';
          visible += 1;
        } else {
          card.style.display = 'none';
        }
      }
      if (counter) {
        counter.textContent = visible + ' / ' + cards.length + ' calculators shown';
      }
    }

    if (searchInput) {
      searchInput.addEventListener('input', applyFilter);
    }
    for (var j = 0; j < pills.length; j += 1) {
      pills[j].addEventListener('click', function () {
        activeCluster = this.getAttribute('data-filter-cluster') || 'all';
        for (var k = 0; k < pills.length; k += 1) {
          pills[k].classList.toggle('active', pills[k] === this);
        }
        applyFilter();
      });
    }
    applyFilter();
  });
})();
