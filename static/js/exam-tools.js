(function (window, document) {
  function toolbar() {
    var el = document.getElementById("examHlToolbar");
    if (el) return el;
    el = document.createElement("div");
    el.id = "examHlToolbar";
    el.className = "hl-toolbar";
    el.hidden = true;
    el.innerHTML =
      '<button type="button" class="hl-btn hl-on" data-hl="on"><i class="fa fa-pencil" aria-hidden="true"></i> Highlight</button>' +
      '<button type="button" class="hl-btn hl-off" data-hl="off"><i class="fa fa-times" aria-hidden="true"></i> Clear</button>';
    document.body.appendChild(el);
    el.addEventListener("mousedown", function (e) { e.preventDefault(); });
    return el;
  }

  function inRoot(node, root) {
    if (!node) return false;
    if (node.nodeType === 3) node = node.parentNode;
    return root.contains(node);
  }

  function unwrap(mark) {
    var parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize();
  }

  function currentRange(root) {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount || sel.isCollapsed) return null;
    var range = sel.getRangeAt(0);
    var node = range.commonAncestorContainer;
    if (node.nodeType === 3) node = node.parentNode;
    if (node && node.closest && node.closest("textarea, input, select, button")) return null;
    if (!inRoot(range.commonAncestorContainer, root)) return null;
    return range;
  }

  function highlight(root) {
    var range = currentRange(root);
    if (!range) return;
    var mark = document.createElement("mark");
    mark.className = "exam-hl";
    try {
      range.surroundContents(mark);
    } catch (err) {
      mark.appendChild(range.extractContents());
      range.insertNode(mark);
    }
    window.getSelection().removeAllRanges();
  }

  function clearHighlight(root) {
    var range = currentRange(root);
    var marks = Array.prototype.slice.call(root.querySelectorAll("mark.exam-hl"));
    marks.forEach(function (mark) {
      if (!range || range.intersectsNode(mark)) unwrap(mark);
    });
    window.getSelection().removeAllRanges();
  }

  function place(bar, range) {
    var rect = range.getBoundingClientRect();
    var top = rect.top + window.scrollY - bar.offsetHeight - 8;
    var left = rect.left + window.scrollX + rect.width / 2 - bar.offsetWidth / 2;
    if (top < window.scrollY + 8) top = rect.bottom + window.scrollY + 8;
    if (left < 8) left = 8;
    bar.style.top = top + "px";
    bar.style.left = left + "px";
  }

  window.ExamTools = {
    attachHighlight: function (root) {
      if (!root) return;
      var bar = toolbar();
      var hideTimer = null;
      function hide() { bar.hidden = true; }
      function show() {
        var range = currentRange(root);
        if (!range) { hide(); return; }
        bar.hidden = false;
        place(bar, range);
      }
      document.addEventListener("mouseup", function () {
        clearTimeout(hideTimer);
        hideTimer = setTimeout(show, 10);
      });
      document.addEventListener("mousedown", function (e) {
        if (!bar.contains(e.target)) hide();
      });
      bar.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-hl]");
        if (!btn) return;
        if (btn.getAttribute("data-hl") === "on") highlight(root);
        else clearHighlight(root);
        hide();
      });
    },
    attachFontSize: function (selectEl, targetEl) {
      if (!selectEl || !targetEl) return;
      function apply() {
        targetEl.style.fontSize = selectEl.value;
      }
      selectEl.addEventListener("change", apply);
      apply();
    },
    attachSplit: function (splitEl, leftEl, gutterEl) {
      if (!splitEl || !leftEl || !gutterEl) return;
      var dragging = false;
      gutterEl.addEventListener("mousedown", function (e) {
        dragging = true;
        document.body.style.cursor = "col-resize";
        e.preventDefault();
      });
      window.addEventListener("mousemove", function (e) {
        if (!dragging) return;
        var rect = splitEl.getBoundingClientRect();
        var pct = ((e.clientX - rect.left) / rect.width) * 100;
        if (pct < 25) pct = 25;
        if (pct > 75) pct = 75;
        leftEl.style.flex = "0 0 " + pct + "%";
      });
      window.addEventListener("mouseup", function () {
        dragging = false;
        document.body.style.cursor = "";
      });
    },
    attachLockAnswers: function (root) {
      if (!root) return;
      var key = "exam-lock:" + window.location.pathname;
      var locked = {};
      try { locked = JSON.parse(sessionStorage.getItem(key) || "{}"); } catch (e) { locked = {}; }
      function save() { sessionStorage.setItem(key, JSON.stringify(locked)); }
      function lockList(list) {
        if (list) list.classList.add("is-locked");
      }
      root.querySelectorAll(".option-list").forEach(function (list) {
        var first = list.querySelector("input[type=radio]");
        if (!first || first.disabled) return;
        var name = first.name;
        var checked = list.querySelector("input[type=radio]:checked");
        if (locked[name] && !checked) {
          var match = list.querySelector('input[type=radio][value="' + String(locked[name]).replace(/"/g, "") + '"]');
          if (match) {
            match.checked = true;
            checked = match;
          }
        }
        if (checked) {
          locked[name] = checked.value;
          lockList(list);
        }
        list.addEventListener("click", function (e) {
          if (!list.classList.contains("is-locked")) return;
          e.preventDefault();
          e.stopPropagation();
        }, true);
        list.addEventListener("keydown", function (e) {
          if (!list.classList.contains("is-locked")) return;
          e.preventDefault();
        }, true);
        list.addEventListener("change", function (e) {
          var el = e.target;
          if (!el || el.type !== "radio") return;
          locked[el.name] = el.value;
          save();
          lockList(list);
        });
      });
      save();
    }
  };
})(window, document);
