/* Flutter-PDF.js Bridge for Ninja Tutor */

// Helper function to map normalized offset to raw text offset
// This is complex because normalized text collapses whitespace, but raw text doesn't
// For now, return the offset as-is since we're using Range on text nodes directly
// The issue is that the normalized and raw offsets need to align
function findRawOffset(normalizedText, normalizedOffset) {
  // Simple approach: if normalizedOffset is within bounds, return it
  // The real complexity comes from the fact that normalized and raw might have different lengths
  if (normalizedOffset < normalizedText.length) {
    return normalizedOffset;
  }
  return normalizedText.length;
}

// Global variables for tracking
let currentPage = 1;
let pageStartTime = Date.now();
let totalTimeSpent = 0;
let activeTimeSpent = 0;
let idleTimeout = null;
let isIdle = false;
let selectedText = "";
let selectedTextPosition = null;
let bookNotes = []; // Notes for current book
let tooltipTimeout = null; // Timeout for showing tooltip
let highlightTimeout = null; // Timeout for applying highlights

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
    case "loadPDF":
      // Load PDF from blob URL or regular URL
      if (message.url && window.PDFViewerApplication) {
        console.log("📨 Loading PDF from URL:", message.url);
        // Use new API signature with object parameter
        window.PDFViewerApplication.open({ url: message.url })
          .then(() => {
            console.log("✅ PDF loaded successfully");
          })
          .catch((error) => {
            console.error("❌ Failed to load PDF:", error);
          });
      } else {
        console.error(
          "❌ Cannot load PDF: missing URL or PDFViewerApplication not ready"
        );
      }
      break;

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

    case "displayNotes":
      // Store notes and highlight them on current page
      console.log("📝 displayNotes message received!");
      console.log("Message notes:", JSON.stringify(message.notes));
      if (message.notes && Array.isArray(message.notes)) {
        bookNotes = message.notes;
        console.log(
          `📝 Stored ${bookNotes.length} notes. Current page: ${currentPage}`
        );
        console.log("Sample note:", JSON.stringify(bookNotes[0]));
        // Apply highlights after a short delay to ensure page is rendered
        if (highlightTimeout) clearTimeout(highlightTimeout);
        highlightTimeout = setTimeout(() => {
          console.log(`⏰ Highlight timeout triggered for page ${currentPage}`);
          highlightNotesOnPage(currentPage);
        }, 2000);
      } else {
        console.error("❌ displayNotes: invalid notes array", message.notes);
      }
      break;
  }
});

// Page change tracking
function onPageChange(pageNum) {
  console.log(`🔄 onPageChange called: page ${currentPage} → ${pageNum}`);

  const timeSpent = Date.now() - pageStartTime;
  totalTimeSpent += timeSpent;
  activeTimeSpent += isIdle ? timeSpent : timeSpent;

  const pageChangeData = {
    previousPage: currentPage,
    newPage: pageNum,
    timeSpent: Math.round(timeSpent / 1000), // Convert to seconds
    totalTimeSpent: Math.round(totalTimeSpent / 1000),
    activeTimeSpent: Math.round(activeTimeSpent / 1000),
  };

  console.log("📤 Sending pageChange to Flutter:", pageChangeData);
  sendToFlutter("pageChange", pageChangeData);

  currentPage = pageNum;
  pageStartTime = Date.now();

  // Highlight notes on new page
  if (bookNotes.length > 0) {
    if (highlightTimeout) clearTimeout(highlightTimeout);
    highlightTimeout = setTimeout(() => {
      highlightNotesOnPage(pageNum);
    }, 1000);
  }
}

// Idle detection
function resetIdleTimer() {
  if (idleTimeout) {
    clearTimeout(idleTimeout);
  }
  isIdle = false;
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
    timestamp: Date.now(),
  });
}

// Highlight notes on current page
function highlightNotesOnPage(pageNum) {
  console.log(`🎨 Highlighting notes on page ${pageNum}`);

  // Get notes for this page
  const pageNotes = bookNotes.filter((note) => note.page === pageNum);

  if (pageNotes.length === 0) {
    console.log("No notes found for this page");
    return;
  }

  console.log(`Found ${pageNotes.length} notes for page ${pageNum}`);

  // Find all text layers and get the one for the current page
  const allTextLayers = document.querySelectorAll(".textLayer");
  console.log(`Found ${allTextLayers.length} text layers`);

  // PDF.js creates text layers with data-page-number attributes
  const textLayer =
    document.querySelector(`.textLayer[data-page-number="${pageNum}"]`) ||
    document.querySelector(".textLayer");

  if (!textLayer) {
    console.warn("Text layer not found, will retry after page renders");
    console.log(
      "Available text layers:",
      Array.from(document.querySelectorAll(".textLayer")).map((el) => ({
        page: el.getAttribute("data-page-number"),
        text: el.textContent?.substring(0, 100),
      }))
    );
    setTimeout(() => highlightNotesOnPage(pageNum), 1000);
    return;
  }

  console.log(
    `Found text layer for page ${pageNum}, searching for ${pageNotes.length} notes`
  );

  // Check if text nodes exist
  const allTextNodes = [];
  const walker = document.createTreeWalker(
    textLayer,
    NodeFilter.SHOW_TEXT,
    null,
    false
  );
  let node;
  while ((node = walker.nextNode())) {
    allTextNodes.push(node);
  }

  console.log(`Found ${allTextNodes.length} text nodes`);

  // If no text nodes, text layer hasn't rendered yet - retry
  if (allTextNodes.length === 0) {
    console.warn(`⚠️ No text nodes found yet, retrying in 500ms...`);
    setTimeout(() => highlightNotesOnPage(pageNum), 500);
    return;
  }

  // Remove any existing highlights for this page to avoid duplicates
  const existingHighlights = textLayer.querySelectorAll(".note-highlight");
  console.log(
    `Found ${existingHighlights.length} existing highlights to clean up`
  );
  existingHighlights.forEach((h) => {
    // Unwrap the highlight but keep the text
    const parent = h.parentNode;
    while (h.firstChild) {
      parent.insertBefore(h.firstChild, h);
    }
    parent.removeChild(h);
  });

  pageNotes.forEach((note, index) => {
    if (!note.selectedText) {
      console.log(`Note ${index} has no selectedText`);
      return;
    }

    // Normalize whitespace in search text (replace multiple spaces/newlines with single space)
    const searchText = note.selectedText.trim().replace(/\s+/g, " ");
    if (!searchText) {
      console.log(`Note ${index} searchText is empty`);
      return;
    }

    console.log(`Searching for: "${searchText.substring(0, 50)}..."`);
    console.log(`Search text length: ${searchText.length}`);
    console.log(`Using ${allTextNodes.length} text nodes`);

    // Build both normalized and original text with node positions
    let fullText = "";
    let normalizedFullText = "";
    let nodePositions = [];

    for (const textNode of allTextNodes) {
      const rawText = textNode.textContent;
      const normalizedText = rawText.replace(/\s+/g, " ");

      const rawStart = fullText.length;
      const normalizedStart = normalizedFullText.length;

      fullText += rawText;
      normalizedFullText += normalizedText;

      const rawEnd = fullText.length;
      const normalizedEnd = normalizedFullText.length;

      nodePositions.push({
        node: textNode,
        rawStart,
        rawEnd,
        normalizedStart,
        normalizedEnd,
      });
    }

    const textIndex = normalizedFullText.indexOf(searchText);
    console.log(`Text found at index: ${textIndex}`);

    // Try to find exact match, if not found, try fuzzy match
    let matchIndex = textIndex;
    let matchText = searchText;

    if (textIndex === -1) {
      console.warn(
        `Text not found in full text: "${searchText.substring(0, 30)}..."`
      );
      console.log(
        `Full text preview: "${normalizedFullText.substring(0, 200)}..."`
      );
      console.log(`Attempting fuzzy match...`);

      // Try fuzzy match - search for first few words
      const searchWords = searchText.split(" ").filter((w) => w.length > 3);
      if (searchWords.length > 0) {
        const fuzzySearch = searchWords
          .slice(0, Math.min(3, searchWords.length))
          .join(" ");
        const fuzzyIndex = normalizedFullText.indexOf(fuzzySearch);
        if (fuzzyIndex !== -1) {
          console.log(`✅ Found fuzzy match at index: ${fuzzyIndex}`);
          matchIndex = fuzzyIndex;
          matchText = fuzzySearch; // Use shorter match text
        } else {
          console.log(`❌ No match found even with fuzzy search`);
          return;
        }
      } else {
        console.log(`❌ No words long enough for fuzzy matching`);
        return;
      }
    }

    // Find which text node contains the start of our match in normalized text
    for (const {
      node: textNode,
      normalizedStart,
      normalizedEnd,
      rawStart,
    } of nodePositions) {
      if (matchIndex >= normalizedStart && matchIndex < normalizedEnd) {
        // This node contains our text in the normalized version
        const normalizedOffset = matchIndex - normalizedStart;

        // Map back to raw text position
        const rawText = textNode.textContent;
        const normalizedText = rawText.replace(/\s+/g, " ");
        const rawOffset = findRawOffset(normalizedText, normalizedOffset);

        console.log(
          `Found in node at normalized offset ${normalizedOffset}, raw offset ${rawOffset}, match length: ${matchText.length}`
        );
        console.log(`   Raw text node length: ${rawText.length}`);
        console.log(`   Normalized text node length: ${normalizedText.length}`);
        console.log(`   Match text: "${matchText}"`);
        console.log(`   Raw text: "${rawText.substring(0, 100)}..."`);

        // Create range using raw offset
        try {
          const range = document.createRange();
          range.setStart(textNode, rawOffset);

          // Calculate end offset - use matchText length since we're dealing with the actual node text
          const rawEndOffset = Math.min(
            rawOffset + matchText.length,
            rawText.length
          );
          console.log(
            `   Setting range: start=${rawOffset}, end=${rawEndOffset} (match length: ${matchText.length}, text node length: ${rawText.length})`
          );
          range.setEnd(textNode, rawEndOffset);

          const span = document.createElement("span");
          span.className = "note-highlight";
          span.setAttribute("data-note-id", note.id);
          // Use !important to override PDF.js styles
          span.style.setProperty("background-color", "rgba(255, 235, 59, 0.6)", "important");
          span.style.setProperty("cursor", "pointer", "important");
          span.style.setProperty("border-bottom", "2px solid #fbc02d", "important");
          span.style.setProperty("display", "inline-block", "important");

          range.surroundContents(span);

          // Verify the span was added to the DOM
          const addedSpan = textLayer.querySelector(
            `[data-note-id="${note.id}"]`
          );
          if (addedSpan) {
            console.log(
              `✅ Highlight created and verified in DOM for note ${index}`
            );
            console.log(`   Highlighted text: "${addedSpan.textContent}"`);

            // Add event listeners
            span.addEventListener("click", (e) => {
              e.stopPropagation();
              sendToFlutter("noteClicked", {
                noteId: note.id,
                page: pageNum,
              });
            });

            span.addEventListener("mouseenter", () =>
              showNoteTooltip(note, span)
            );
            span.addEventListener("mouseleave", () => hideNoteTooltip());
          } else {
            console.error(
              `❌ Highlight created but not found in DOM for note ${index}`
            );
          }

          break;
        } catch (e) {
          console.error(`❌ Error creating highlight for note ${index}:`, e);
          console.error(`   Error message:`, e.message);
          console.error(`   Stack:`, e.stack);
        }
      }
    }
  });
}

// Show tooltip on hover
function showNoteTooltip(note, element) {
  if (tooltipTimeout) clearTimeout(tooltipTimeout);

  tooltipTimeout = setTimeout(() => {
    const rect = element.getBoundingClientRect();
    const tooltip = document.createElement("div");
    tooltip.className = "note-tooltip";
    tooltip.style.cssText =
      "position: fixed; background: white; border: 1px solid #ccc; padding: 8px 12px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2); z-index: 10000; max-width: 250px; font-size: 13px;";
    tooltip.innerHTML = `
      <div style="font-weight: bold; margin-bottom: 4px;">${(
        note.title || "Untitled Note"
      )
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")}</div>
      <div style="font-size: 0.9em; color: #666;">${note.content
        .substring(0, 100)
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")}${note.content.length > 100 ? "..." : ""}</div>
    `;
    tooltip.style.left = rect.right + 10 + "px";
    tooltip.style.top = rect.top + "px";
    document.body.appendChild(tooltip);
  }, 500);
}

// Hide tooltip
function hideNoteTooltip() {
  if (tooltipTimeout) clearTimeout(tooltipTimeout);
  const tooltip = document.querySelector(".note-tooltip");
  if (tooltip) tooltip.remove();
}

// Track if PDF.js event listeners are set up
let pdfEventListenersSetup = false;

// Initialize Flutter bridge
function initializeFlutterBridge() {
  console.log("Initializing Flutter Bridge...");

  // User interaction events for idle detection (only set up once)
  if (!pdfEventListenersSetup) {
    ["mousedown", "mousemove", "keypress", "scroll", "touchstart"].forEach(
      (event) => {
        document.addEventListener(event, resetIdleTimer, true);
      }
    );

    // Text selection events
    document.addEventListener("mouseup", onTextSelection);
    document.addEventListener("selectionchange", onTextSelection);
  }

  // Try to set up PDF.js events if available, but don't fail if not ready yet
  if (
    window.PDFViewerApplication &&
    window.PDFViewerApplication.eventBus &&
    !pdfEventListenersSetup
  ) {
    const eventBus = window.PDFViewerApplication.eventBus;

    try {
      // Page change event
      eventBus.on("pagechanging", function (evt) {
        console.log(
          `📄 PDF.js page changing from ${currentPage} to ${evt.pageNumber}`
        );
        onPageChange(evt.pageNumber);
      });

      // Initial page
      currentPage = window.PDFViewerApplication.page || 1;
      pageStartTime = Date.now();

      console.log("✅ Event listeners set up successfully");
      pdfEventListenersSetup = true;
    } catch (error) {
      console.error("❌ Error setting up event listeners:", error);
    }
  } else if (!pdfEventListenersSetup) {
    console.log("⏳ PDFViewerApplication not ready, retrying in 500ms");
    setTimeout(initializeFlutterBridge, 500);
  }

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
  highlightNotesOnPage: highlightNotesOnPage,
};

// Start initialization
initializeFlutterBridge();

// Also try when window loads
window.addEventListener("load", function () {
  console.log("Window loaded, re-initializing Flutter Bridge");
  initializeFlutterBridge();
});

// Listen for PDF.js viewer ready event
window.addEventListener("webviewerloaded", function () {
  console.log("PDF.js viewer loaded, initializing Flutter Bridge");
  initializeFlutterBridge();
});
