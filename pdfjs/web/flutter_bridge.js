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

    case "setScrollEnabled":
      // Enable or disable scrolling in the PDF viewer
      const container = document.getElementById("viewerContainer");
      if (container) {
        if (message.enabled) {
          container.style.overflow = "auto";
          container.style.pointerEvents = "auto";
          console.log("✅ PDF scrolling enabled");
        } else {
          container.style.overflow = "hidden";
          container.style.pointerEvents = "none";
          console.log("🚫 PDF scrolling disabled");
        }
      }
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

// Text selection tracking with page coordinates
function onTextSelection() {
  const selection = window.getSelection();
  selectedText = selection.toString().trim();

  if (selectedText) {
    // Get selection position (viewport coordinates)
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    // Try to get PDF page coordinates
    const pageCoordinates = getPdfPageCoordinates(rect);

    selectedTextPosition = {
      // Viewport coordinates
      viewportX: rect.left,
      viewportY: rect.top,
      width: rect.width,
      height: rect.height,
      // PDF page coordinates (if available)
      ...pageCoordinates,
    };

    sendToFlutter("textSelection", {
      text: selectedText,
      page: currentPage,
      position: selectedTextPosition,
      charCount: selectedText.length,
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

// Convert viewport coordinates to PDF page coordinates
function getPdfPageCoordinates(rect) {
  try {
    if (
      !window.PDFViewerApplication ||
      !window.PDFViewerApplication.pdfViewer
    ) {
      return {};
    }

    const viewer = window.PDFViewerApplication.pdfViewer;
    const page = viewer.getPageView(currentPage - 1); // 0-indexed

    if (!page || !page.viewport) {
      return {};
    }

    // Get page container position
    const pageElement = page.div;
    const pageRect = pageElement.getBoundingClientRect();

    // Calculate relative position within the page
    const relativeX = rect.left - pageRect.left;
    const relativeY = rect.top - pageRect.top;

    // Convert to PDF coordinates (PDF origin is bottom-left)
    const viewport = page.viewport;
    const pdfX = relativeX / viewport.scale;
    const pdfY = (pageRect.height - relativeY) / viewport.scale;

    return {
      pdfX: Math.round(pdfX),
      pdfY: Math.round(pdfY),
      pdfWidth: Math.round(rect.width / viewport.scale),
      pdfHeight: Math.round(rect.height / viewport.scale),
      scale: viewport.scale,
    };
  } catch (error) {
    console.error("Error getting PDF coordinates:", error);
    return {};
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

// Track existing annotations on a page
function trackAnnotations(pageNumber) {
  try {
    const viewer = window.PDFViewerApplication.pdfViewer;
    const pageView = viewer.getPageView(pageNumber - 1);

    if (!pageView || !pageView.annotationLayer) {
      return;
    }

    // Get all annotation elements
    const annotationElements = pageView.annotationLayer.div.querySelectorAll(
      ".annotationLayer > section"
    );

    console.log(
      `Found ${annotationElements.length} annotations on page ${pageNumber}`
    );
  } catch (error) {
    console.error("Error tracking annotations:", error);
  }
}

// Capture editor annotations (drawings, text added by user)
function captureEditorAnnotations(pageNumber) {
  try {
    const viewer = window.PDFViewerApplication.pdfViewer;
    const pageView = viewer.getPageView(pageNumber - 1);

    if (!pageView || !pageView.annotationEditorLayer) {
      return;
    }

    // Get all editor annotations
    const editorLayer = pageView.annotationEditorLayer.div;
    const editors = editorLayer.querySelectorAll(
      ".annotationEditorLayer > div"
    );

    editors.forEach((editor) => {
      captureAnnotationData(editor, pageNumber);
    });
  } catch (error) {
    console.error("Error capturing editor annotations:", error);
  }
}

// Capture data from a specific annotation element
function captureAnnotationData(element, pageNumber) {
  try {
    const annotationType =
      element.getAttribute("data-editor-type") || "unknown";
    const rect = element.getBoundingClientRect();
    const pageCoordinates = getPdfPageCoordinates(rect);

    let annotationData = {
      type: annotationType,
      page: pageNumber,
      position: {
        viewportX: rect.left,
        viewportY: rect.top,
        width: rect.width,
        height: rect.height,
        ...pageCoordinates,
      },
      timestamp: Date.now(),
    };

    // Extract annotation-specific data
    if (annotationType === "freetext") {
      // Text annotation
      const textElement = element.querySelector(".internal");
      annotationData.text = textElement ? textElement.textContent : "";
      annotationData.fontSize = window.getComputedStyle(
        textElement || element
      ).fontSize;
      annotationData.color = window.getComputedStyle(element).color;
    } else if (annotationType === "ink") {
      // Drawing/ink annotation
      const canvas = element.querySelector("canvas");
      if (canvas) {
        annotationData.drawingData = canvas.toDataURL("image/png");
        annotationData.width = canvas.width;
        annotationData.height = canvas.height;
      }
    } else if (annotationType === "highlight") {
      // Highlight annotation
      annotationData.color = window.getComputedStyle(element).backgroundColor;
    }

    sendToFlutter("annotation", annotationData);
    console.log("Captured annotation:", annotationType, "on page", pageNumber);
  } catch (error) {
    console.error("Error capturing annotation data:", error);
  }
}

// Capture all annotations from all pages
function captureAllAnnotations() {
  try {
    if (
      !window.PDFViewerApplication ||
      !window.PDFViewerApplication.pdfViewer
    ) {
      // Only log if this is unexpected
      return;
    }

    const viewer = window.PDFViewerApplication.pdfViewer;
    let totalAnnotations = 0;

    // Loop through all rendered pages
    for (let i = 0; i < viewer._pages.length; i++) {
      const pageView = viewer._pages[i];

      if (!pageView) {
        continue;
      }

      // Check for annotation editor layer (silently skip if not present)
      if (!pageView.annotationEditorLayer) {
        continue;
      }

      const editorLayer = pageView.annotationEditorLayer.div;
      if (!editorLayer) {
        continue;
      }

      // Look for various annotation element patterns
      const editors = editorLayer.querySelectorAll(
        'section, div[class*="Editor"], *[data-editor-rotation]'
      );

      // Only log if we actually found annotations
      if (editors.length === 0) {
        continue;
      }

      console.log(`📝 Page ${i + 1}: Found ${editors.length} annotations`);

      editors.forEach((editor, idx) => {
        const alreadySent = editor.getAttribute("data-sent-to-flutter");

        // Only process new annotations
        if (alreadySent) {
          return; // Skip already sent annotations silently
        }

        // Determine annotation type from class or data attributes
        let annotationType = editor.getAttribute("data-editor-type");
        if (!annotationType) {
          if (editor.className.includes("freeText"))
            annotationType = "freetext";
          else if (editor.className.includes("ink")) annotationType = "ink";
          else annotationType = "unknown";
        }

        const id =
          editor.getAttribute("data-annotation-id") ||
          `${Date.now()}-${Math.random()}`;

        // Log and capture new annotation
        console.log(`✨ NEW ANNOTATION: type=${annotationType}, page=${i + 1}`);
        editor.setAttribute("data-sent-to-flutter", "true");
        editor.setAttribute("data-annotation-id", id);
        captureAnnotationData(editor, i + 1);
        totalAnnotations++;
      });
    }

    if (totalAnnotations > 0) {
      console.log(`✅ Captured ${totalAnnotations} new annotations`);
    }
  } catch (error) {
    console.error("❌ Error capturing annotations:", error);
    console.error(error.stack);
  }
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
      const eventBus = window.PDFViewerApplication.eventBus;

      eventBus.on("pagechanging", (evt) => {
        onPageChange(evt.pageNumber);
      });

      // Annotation events
      eventBus.on("annotationlayerrendered", (evt) => {
        console.log("Annotation layer rendered for page", evt.pageNumber);
        trackAnnotations(evt.pageNumber);
      });

      // Listen for annotation editor events (drawing, text)
      if (window.PDFViewerApplication.pdfViewer) {
        const viewer = window.PDFViewerApplication.pdfViewer;

        // Monitor for annotation changes
        eventBus.on("annotationeditorlayerrendered", (evt) => {
          console.log(
            "Annotation editor layer rendered for page",
            evt.pageNumber
          );
          captureEditorAnnotations(evt.pageNumber);
        });
      }

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

  // Monitor for annotation changes periodically
  setInterval(captureAllAnnotations, 2000); // Check every 2 seconds

  // Initialize idle timer
  resetIdleTimer();

  // Send initial state
  sendToFlutter("pdfReady", {
    totalPages: window.PDFViewerApplication
      ? window.PDFViewerApplication.pagesCount
      : 0,
    currentPage: currentPage,
  });

  // Diagnostic logging (reduced verbosity)
  console.log("✅ PDF Bridge initialized - ready to capture annotations");

  // Debug mode can be enabled by setting window.DEBUG_PDF_BRIDGE = true
  if (window.DEBUG_PDF_BRIDGE) {
    console.log("📚 ===== PDF Annotation Capture System =====");
    console.log(`📄 Total pages: ${window.PDFViewerApplication.pagesCount}`);
    console.log(`📍 Current page: ${currentPage}`);
    console.log("🔄 Checking for annotations every 2 seconds...");
    console.log("==========================================");

    // Check if annotation mode is available
    setTimeout(() => {
      const viewer = window.PDFViewerApplication.pdfViewer;
      console.log("🔍 PDF.js Editor Mode Status:");
      console.log(
        "   annotationEditorMode:",
        window.PDFViewerApplication.pdfViewer.annotationEditorMode
      );
      console.log(
        "   annotationEditorParams:",
        window.PDFViewerApplication.annotationEditorParams
      );

      // List all pages and their editor layers
      viewer._pages.forEach((page, idx) => {
        if (page.annotationEditorLayer) {
          console.log(`   Page ${idx + 1}: annotationEditorLayer EXISTS ✅`);
        } else {
          console.log(`   Page ${idx + 1}: annotationEditorLayer MISSING ❌`);
        }
      });
    }, 3000);
  }
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
