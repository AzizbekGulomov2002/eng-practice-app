(function () {
  var el = document.getElementById("writing-timer");
  if (!el) return;
  var form = document.getElementById("writing-form");
  var total = parseInt(el.getAttribute("data-seconds"), 10) || 0;
  var key = el.getAttribute("data-key") || "";
  var stored = parseInt(sessionStorage.getItem(key) || "", 10);
  var remaining = (!isNaN(stored) && stored >= 0 && stored <= total) ? stored : total;

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }
  function label(sec) {
    sec = Math.max(0, sec);
    var h = Math.floor(sec / 3600);
    var m = Math.floor((sec % 3600) / 60);
    var s = sec % 60;
    if (h > 0) return h + ":" + pad(m) + ":" + pad(s);
    return pad(m) + ":" + pad(s);
  }
  function render() {
    el.innerHTML = '<i class="fa fa-clock-o" aria-hidden="true"></i> Time Left: ' + label(remaining);
    if (remaining <= 600) el.classList.add("is-low");
    else el.classList.remove("is-low");
  }
  function finish() {
    if (key) sessionStorage.removeItem(key);
    if (!form) return;
    if (!form.querySelector('input[name="timed_out"]')) {
      var input = document.createElement("input");
      input.type = "hidden";
      input.name = "timed_out";
      input.value = "1";
      form.appendChild(input);
    }
    form.submit();
  }
  function tick() {
    render();
    if (remaining <= 0) {
      finish();
      return;
    }
    remaining -= 1;
    if (key) sessionStorage.setItem(key, String(remaining));
    setTimeout(tick, 1000);
  }
  tick();
})();
