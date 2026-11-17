let noticeTimer;

export function $(id) {
  return document.getElementById(id);
}

export function notify(message, error = false) {
  clearTimeout(noticeTimer);
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "";
  $("notice").hidden = false;
  noticeTimer = setTimeout(() => { $("notice").hidden = true; }, error ? 10000 : 4000);
}
