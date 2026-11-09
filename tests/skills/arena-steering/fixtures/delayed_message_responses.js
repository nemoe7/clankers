(() => {
  window.holdLatest = false;
  window.heldLatest = [];
  window.wsPaths = new Map();
  window.taskResponses = 0;
  const taskRequests = new Set();
  const interval = window.setInterval.bind(window);
  window.setInterval = (callback, delay, ...args) => {
    if (delay === 3000 && String(callback).includes("changeHandler")) {
      window.pollTick = callback;
    }
    return interval(callback, delay, ...args);
  };
  const fetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await fetch(...args);
    const path = String(args[0]);
    const json = response.json.bind(response);
    if (path.startsWith("/messages?") && window.holdLatest) {
      response.json = () => new Promise(resolve => {
        window.heldLatest.push(() => resolve(json()));
      });
    } else if (path.startsWith("/tasks?")) {
      response.json = async () => {
        const payload = await json();
        window.taskResponses += 1;
        return payload;
      };
    }
    return response;
  };
  const prototype = window.WebSocket.prototype;
  const send = prototype.send;
  prototype.send = function(data) {
    window.probeSocket = this;
    try {
      const request = JSON.parse(data);
      if (request.path?.startsWith("/messages?")) {
        window.wsPaths.set(request.id, request.path);
      }
      if (request.path?.startsWith("/tasks?")) taskRequests.add(request.id);
    } catch {}
    return send.call(this, data);
  };
  const add = prototype.addEventListener;
  prototype.addEventListener = function(type, listener, options) {
    if (type !== "message") return add.call(this, type, listener, options);
    return add.call(this, type, function(event) {
      let response;
      try { response = JSON.parse(event.data); } catch {}
      if (response?.type === "response" && taskRequests.delete(response.id)) {
        window.taskResponses += 1;
      }
      if (window.holdLatest && response?.type === "response" && window.wsPaths.has(response.id)) {
        window.heldLatest.push(() => listener.call(this, event));
        return;
      }
      return listener.call(this, event);
    }, options);
  };
  window.refreshProbe = () => {
    if (window.probeSocket?.readyState === 1) {
      window.probeSocket.dispatchEvent(new MessageEvent("message", {
        data: JSON.stringify({ type: "change" }),
      }));
    } else {
      window.pollTick?.();
    }
  };
})();
