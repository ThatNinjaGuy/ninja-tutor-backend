/* Flutter-PDF.js Bridge for Ninja Tutor */

// Global variables for tracking
let currentPage = 1;
let pageStartTime = Date.now();
let totalTimeSpent = 0;
let activeTimeSpent = 0;
let idleTimeout = null;
let isIdle = false;
let selectedText = "";
let selectedTextPosition = null;

// Flutter communication
function sendToFlutter(type, data) {
  const message = {
    type: type,
    timestamp: Date.now(),
    ...data,
  };

  // Send to parent window (Flutter)
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(message, "*");
  }

  console.log("Sending to Flutter:", message);
}

// Receive commands from Flutter
window.addEventListener("message", function (event) {
  const message = event.data;
  console.log("Received from Flutter:", message);

  switch (message.type) {
    case "goToPage":
      if (
        window.PDFViewerApplication &&
        window.PDFViewerApplication.page !== message.page
      ) {
        window.PDFViewerApplication.page = message.page;
      }
      break;

    case "setZoom":
      if (window.PDFViewerApplication) {
        window.PDFViewerApplication.pdfViewer.currentScale = message.zoom;
      }
      break;

    case "addBookmark":
      sendToFlutter("bookmarkAdded", {
        page: currentPage,
        timestamp: Date.now(),
      });
      break;

    case "toggleHighlightMode":
      // Toggle highlight mode
      const highlightMode = !document.body.classList.contains("highlight-mode");
      document.body.classList.toggle("highlight-mode", highlightMode);
      sendToFlutter("highlightModeChanged", { enabled: highlightMode });
      break;
  }
});

// Page change tracking
function onPageChange(pageNum) {
  const timeSpent = Date.now() - pageStartTime;
  totalTimeSpent += timeSpent;

  if (!isIdle) {
    activeTimeSpent += timeSpent;
  }

  // Send time data to Flutter
  sendToFlutter("pageChange", {
    previousPage: currentPage,
    newPage: pageNum,
    timeSpent: Math.round(timeSpent / 1000), // Convert to seconds
    totalTimeSpent: Math.round(totalTimeSpent / 1000),
    activeTimeSpent: Math.round(activeTimeSpent / 1000),
  });

  currentPage = pageNum;
  pageStartTime = Date.now();
}

// Idle detection
function resetIdleTimer() {
  if (idleTimeout) {
    clearTimeout(idleTimeout);
  }

  const wasIdle = isIdle;
  isIdle = false;

  if (wasIdle) {
    sendToFlutter("idleStateChange", { isIdle: false });
  }

  // Set idle after 10 seconds of no interaction
  idleTimeout = setTimeout(() => {
    isIdle = true;
    sendToFlutter("idleStateChange", { isIdle: true });
  }, 10000);
}

// Text selection tracking
function onTextSelection() {
  const selection = window.getSelection();
  selectedText = selection.toString().trim();

  if (selectedText) {
    // Get selection position
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    selectedTextPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height,
    };

    sendToFlutter("textSelection", {
      text: selectedText,
      page: currentPage,
      position: selectedTextPosition,
    });
  } else {
    selectedText = "";
    selectedTextPosition = null;
    sendToFlutter("textSelection", {
      text: "",
      page: currentPage,
      position: null,
    });
  }
}

// Highlight functionality
function createHighlight(text, color = "yellow") {
  if (!selectedText || !selectedTextPosition) {
    return;
  }

  sendToFlutter("highlight", {
    text: selectedText,
    page: currentPage,
    color: color,
    position: selectedTextPosition,
  });

  // Clear selection
  window.getSelection().removeAllRanges();
  selectedText = "";
  selectedTextPosition = null;
}

// Initialize when PDF.js is ready
function initializeFlutterBridge() {
  console.log("Initializing Flutter Bridge...");

  // Wait for PDF.js to be ready
  if (window.PDFViewerApplication && window.PDFViewerApplication.eventBus) {
    setupEventListeners();
  } else {
    // Wait for PDF.js to load - check multiple times
    let attempts = 0;
    const maxAttempts = 20;
    const checkInterval = setInterval(() => {
      attempts++;
      if (window.PDFViewerApplication && window.PDFViewerApplication.eventBus) {
        clearInterval(checkInterval);
        setupEventListeners();
      } else if (attempts >= maxAttempts) {
        clearInterval(checkInterval);
        console.error("PDF.js did not initialize in time");
      }
    }, 500);
  }
}

function setupEventListeners() {
  console.log("Setting up event listeners...");

  // Page change events
  if (window.PDFViewerApplication && window.PDFViewerApplication.eventBus) {
    try {
      window.PDFViewerApplication.eventBus.on("pagechanging", (evt) => {
        onPageChange(evt.pageNumber);
      });

      // Initial page
      currentPage = window.PDFViewerApplication.page || 1;
      pageStartTime = Date.now();

      console.log("Event listeners set up successfully");
    } catch (error) {
      console.error("Error setting up event listeners:", error);
    }
  } else {
    console.error("PDFViewerApplication or eventBus not available");
    return;
  }

  // User interaction events for idle detection
  ["mousedown", "mousemove", "keypress", "scroll", "touchstart"].forEach(
    (event) => {
      document.addEventListener(event, resetIdleTimer, true);
    }
  );

  // Text selection events
  document.addEventListener("mouseup", onTextSelection);
  document.addEventListener("selectionchange", onTextSelection);

  // Initialize idle timer
  resetIdleTimer();

  // Send initial state
  sendToFlutter("pdfReady", {
    totalPages: window.PDFViewerApplication
      ? window.PDFViewerApplication.pagesCount
      : 0,
    currentPage: currentPage,
  });
}

// Global functions for external access
window.FlutterBridge = {
  createHighlight: createHighlight,
  sendToFlutter: sendToFlutter,
  onPageChange: onPageChange,
  onTextSelection: onTextSelection,
};

// Start initialization
initializeFlutterBridge();

// Also try when window loads
window.addEventListener("load", () => {
  setTimeout(setupEventListeners, 500);
});
