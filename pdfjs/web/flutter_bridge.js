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
const PAGE_ICON_SYMBOL = "★";
const bookmarkedPages = new Set();
let isTooltipInteractionActive = false;
let tooltipInteractionTimeout = null;
const DEFAULT_HIGHLIGHT_COLOR = "#4CAF50";
const DEFAULT_HIGHLIGHT_BORDER = "#2E7D32";
const DEFAULT_HIGHLIGHT_RGBA = "rgba(76, 175, 80, 0.7)";

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForTextLayerReady(pageNum, retries = 20, delayMs = 100) {
  const pdfApp = window.PDFViewerApplication;
  const pdfViewer = pdfApp?.pdfViewer;
  let pageView = null;

  async function ensurePageView() {
    if (!pdfViewer) {
      return;
    }
    try {
      if (typeof pdfViewer._ensurePdfPageLoaded === "function") {
        await pdfViewer._ensurePdfPageLoaded(pageNum);
      } else if (pdfApp?.pdfDocument) {
        await pdfApp.pdfDocument.getPage(pageNum);
      }
    } catch (err) {
      console.warn(`⚠️ Failed to ensure page ${pageNum} is loaded`, err);
    }

    pageView = pdfViewer.getPageView?.(pageNum - 1) ?? pdfViewer._pages?.[pageNum - 1] ?? null;
    if (!pageView) {
      return;
    }

    try {
      const renderingStates = window.pdfjsViewer?.RenderingStates;
      if (renderingStates && pageView.renderingState !== renderingStates.FINISHED) {
        await pageView.pdfPageRender?.promise;
      } else if (!renderingStates && pageView.pdfPageRender?.promise) {
        await pageView.pdfPageRender.promise;
      }
    } catch (err) {
      console.warn(`⚠️ Error waiting for page render on page ${pageNum}`, err);
    }

    if (typeof pdfViewer._forceRendering === "function") {
      try {
        pdfViewer._forceRendering();
      } catch (err) {
        console.warn("⚠️ _forceRendering threw an error", err);
      }
    }

    const textLayer = pageView.textLayer;
    if (textLayer && textLayer.renderingDone === false && textLayer.renderingDonePromise) {
      try {
        await textLayer.renderingDonePromise;
      } catch (err) {
        console.warn(`⚠️ Error waiting for text layer render on page ${pageNum}`, err);
      }
    }
  }

  await ensurePageView();

  for (let attempt = 0; attempt < retries; attempt++) {
    pageView = pdfViewer?.getPageView?.(pageNum - 1) ?? pdfViewer?._pages?.[pageNum - 1] ?? pageView;
    if (pageView?.textLayer) {
      const textLayerObj = pageView.textLayer;
      const spansFromTextLayer = Array.from(textLayerObj.textDivs ?? []).filter(
        (node) => node && node.textContent && node.textContent.trim()
      );
      if (spansFromTextLayer.length > 0) {
        const layerElement = textLayerObj.div ?? textLayerObj.textLayerDiv ?? spansFromTextLayer[0]?.parentNode ?? null;
        return { textLayer: layerElement, spans: spansFromTextLayer };
      }
    }

    const domLayer =
      document.querySelector(`.page[data-page-number="${pageNum}"] .textLayer`) ||
      document.querySelector(`.textLayer[data-page-number="${pageNum}"]`) ||
      pageView?.textLayer?.div ||
      null;

    if (domLayer) {
      let domSpans = Array.from(domLayer.querySelectorAll('span[role="presentation"]'));
      if (domSpans.length === 0) {
        domSpans = Array.from(domLayer.querySelectorAll('span'));
      }
      if (domSpans.length === 0 && domLayer.childNodes?.length) {
        domSpans = Array.from(domLayer.childNodes).filter(
          (node) => node.nodeType === Node.ELEMENT_NODE && node.textContent?.trim()
        );
      }
      if (domSpans.length > 0) {
        return { textLayer: domLayer, spans: domSpans };
      }
    }

    if (attempt === 0) {
      await ensurePageView();
    }

    await delay(delayMs);
  }

  return { textLayer: pageView?.textLayer?.div ?? null, spans: [] };
}

function resolveNotePage(note) {
  if (!note) return NaN;
  const rawPage =
    note.page ??
    note.pageNumber ??
    note.page_number ??
    (note.position &&
      (note.position.page ?? note.position.pageNumber ?? note.position.page_number));
  const parsed = Number(rawPage);
  return Number.isNaN(parsed) ? NaN : parsed;
}

function resolveNoteText(note) {
  if (!note) return "";
  const candidates = [
    note.selectedText,
    note.text,
    note.content,
    note.highlightText,
  ];
  for (const value of candidates) {
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }
  return "";
}

function ensurePageIcon(pageNum) {
  if (!pageNum || Number.isNaN(pageNum)) {
    return;
  }

  const pageElement = document.querySelector(
    `.page[data-page-number="${pageNum}"]`
  );

  if (!pageElement) {
    return;
  }

  let icon = pageElement.querySelector(".ninja-page-icon");
  if (!icon) {
    icon = document.createElement("div");
    icon.className = "ninja-page-icon";
    icon.textContent = PAGE_ICON_SYMBOL;
    icon.setAttribute("data-page", pageNum.toString());
    icon.setAttribute("role", "button");
    icon.setAttribute("tabindex", "0");

    icon.addEventListener("click", (e) => {
      e.stopPropagation();
      sendToFlutter("toggleBookmark", {
        page: pageNum,
      });
    });

    icon.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        icon.click();
      }
    });

    pageElement.appendChild(icon);
  }

  updateBookmarkIconState(icon, pageNum);
}

function updateBookmarkIconState(icon, pageNum) {
  if (!icon) {
    return;
  }

  const numericPage = Number(pageNum);
  const isBookmarked = bookmarkedPages.has(numericPage);
  icon.classList.toggle("is-bookmarked", isBookmarked);
  icon.setAttribute("aria-pressed", isBookmarked ? "true" : "false");
  icon.setAttribute(
    "title",
    isBookmarked
      ? `Remove bookmark for page ${numericPage}`
      : `Add bookmark for page ${numericPage}`
  );
}

function addIconsToAllPages() {
  const pages = document.querySelectorAll(".page[data-page-number]");
  pages.forEach((page) => {
    const pageNum = parseInt(page.getAttribute("data-page-number"), 10);
    ensurePageIcon(pageNum);
  });
}

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

    case "createHighlight":
      createHighlight({
        text: message.text,
        color: message.color,
        position: message.position,
      });
      break;

    case "bookmarkStateUpdate":
      if (Array.isArray(message.pages)) {
        bookmarkedPages.clear();
        message.pages.forEach((page) => {
          const numericPage = parseInt(page, 10);
          if (!Number.isNaN(numericPage)) {
            bookmarkedPages.add(numericPage);
          }
        });
        addIconsToAllPages();
      }
      break;

    case "bookmarkStatus":
      if (typeof message.page === "number") {
        const pageNum = message.page;
        if (message.isBookmarked) {
          bookmarkedPages.add(pageNum);
        } else {
          bookmarkedPages.delete(pageNum);
        }

        const pageElement = document.querySelector(
          `.page[data-page-number="${pageNum}"]`
        );
        if (pageElement) {
          const icon = pageElement.querySelector(".ninja-page-icon");
          if (icon) {
            updateBookmarkIconState(icon, pageNum);
            icon.classList.add("bookmark-feedback");
            setTimeout(() => icon.classList.remove("bookmark-feedback"), 250);
          }
        }
      }
      break;

    case "displayNotes":
      // Store notes and highlight them on current page
      console.log("📝 displayNotes message received!");
      console.log("Message notes:", JSON.stringify(message.notes));
      if (message.notes && Array.isArray(message.notes)) {
        // Clear all existing highlights before applying new ones
        clearAllHighlights();
        
        bookNotes = message.notes;
        console.log(
          `📝 Stored ${bookNotes.length} notes. Current page: ${currentPage}`
        );
        console.log("Sample note:", JSON.stringify(bookNotes[0]));
        addIconsToAllPages();
        // Highlights will be applied when textlayerrendered event fires
        console.log("✅ Notes stored, re-highlighting current page");
        highlightNotesOnPage(currentPage);
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
  ensurePageIcon(pageNum);

  // Highlights will be applied when textlayerrendered event fires for this page
  console.log(`📄 Page changed to ${pageNum}, waiting for textlayerrendered event`);
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
function getSelectionBoundingRect(range) {
  if (!range) {
    return null;
  }

  const rects = range.getClientRects();
  if (!rects || rects.length === 0) {
    const rect = range.getBoundingClientRect();
    if (!rect) {
      return null;
    }
    return {
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
    };
  }

  let left = Number.POSITIVE_INFINITY;
  let right = Number.NEGATIVE_INFINITY;
  let top = Number.POSITIVE_INFINITY;
  let bottom = Number.NEGATIVE_INFINITY;

  for (let i = 0; i < rects.length; i++) {
    const rect = rects[i];
    if (!rect || (rect.width === 0 && rect.height === 0)) {
      continue;
    }

    if (rect.left < left) left = rect.left;
    if (rect.right > right) right = rect.right;
    if (rect.top < top) top = rect.top;
    if (rect.bottom > bottom) bottom = rect.bottom;
  }

  if (!Number.isFinite(left) || !Number.isFinite(right)) {
    return null;
  }

  return {
    left,
    top,
    right,
    bottom,
    width: right - left,
    height: bottom - top,
  };
}

function onTextSelection() {
  const selection = window.getSelection();
  if (!selection) {
    return;
  }

  const selectionText = selection.toString().trim();

  if (selectionText) {
    const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
    const rect = getSelectionBoundingRect(range);

    selectedText = selectionText;
    if (rect) {
      selectedTextPosition = {
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height,
      };
    } else {
      selectedTextPosition = null;
    }

    sendToFlutter("textSelection", {
      text: selectedText,
      page: currentPage,
      position: selectedTextPosition,
    });

    // Show selection tooltip after a brief delay (to avoid showing during selection drag)
    setTimeout(() => {
      const currentSelection = window.getSelection();
      if (currentSelection && currentSelection.toString().trim()) {
        const currentRange = currentSelection.getRangeAt(0);
        const currentRect = getSelectionBoundingRect(currentRange);
        if (currentRect) {
          showSelectionTooltip(currentSelection, currentRect);
        }
      }
    }, 100);
  } else {
    if (currentTooltip || isTooltipInteractionActive) {
      return;
    }

    selectedText = "";
    selectedTextPosition = null;
    hideSelectionTooltip();
    sendToFlutter("textSelection", {
      text: "",
      page: currentPage,
      position: null,
    });
  }
}

// Highlight functionality
function createHighlight(options = {}) {
  const providedColor = options.color;
  const highlightColor =
    typeof providedColor === "string" && providedColor.trim().length > 0
      ? providedColor.trim()
      : DEFAULT_HIGHLIGHT_COLOR;

  const textOverride =
    typeof options.text === "string" && options.text.trim().length > 0
      ? options.text.trim()
      : null;

  const highlightText = textOverride || selectedText?.trim() || "";
  const highlightPosition = options.position || selectedTextPosition;

  if (!highlightText || !highlightPosition) {
    console.warn(
      "⚠️ Cannot create highlight: missing text or selection position",
      {
        highlightText,
        highlightPosition,
      }
    );
    return;
  }

  // Update globals to ensure the stored selection matches what we save
  selectedText = highlightText;
  selectedTextPosition = highlightPosition;
  ensurePageIcon(currentPage);

  const highlightPayload = {
    text: highlightText,
    page: currentPage,
    color: highlightColor,
    position: highlightPosition,
    timestamp: Date.now(),
  };

  sendToFlutter("highlight", highlightPayload);

  // Provide immediate feedback by rendering the highlight locally
  const tempHighlight = {
    id: `temp-highlight-${highlightPayload.timestamp}`,
    page: currentPage,
    selectedText: highlightText,
    content: highlightText,
    color: highlightColor,
    source: "temp-highlight",
  };

  bookNotes = [...bookNotes, tempHighlight];
  highlightNotesOnPage(currentPage);

  const selection = window.getSelection();
  if (selection) {
    selection.removeAllRanges();
  }
  selectedText = "";
  selectedTextPosition = null;
  setTooltipInteractionActive(false);
  sendToFlutter("textSelection", {
    text: "",
    page: currentPage,
    position: null,
  });
}

function hexToRgba(hex, alpha = 0.5) {
  if (typeof hex !== "string") {
    return DEFAULT_HIGHLIGHT_RGBA;
  }

  const sanitized = hex.replace("#", "");
  if (sanitized.length !== 6) {
    return DEFAULT_HIGHLIGHT_RGBA;
  }

  const bigint = parseInt(sanitized, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function resolveHighlightStyle(note) {
  const palette = {
    yellow: { background: "rgba(255, 235, 59, 0.65)", border: "#F9A825" },
    green: { background: "rgba(102, 187, 106, 0.6)", border: "#43A047" },
    blue: { background: "rgba(66, 165, 245, 0.6)", border: "#1976d2" },
    pink: { background: "rgba(236, 64, 122, 0.5)", border: "#C2185B" },
    orange: { background: "rgba(255, 152, 0, 0.6)", border: "#EF6C00" },
    purple: { background: "rgba(171, 71, 188, 0.55)", border: "#7B1FA2" },
  };

  const rawColor =
    (typeof note.color === "string" &&
      note.color.trim().length > 0 &&
      note.color.trim()) ||
    (note.style &&
      typeof note.style.color === "string" &&
      note.style.color.trim()) ||
    DEFAULT_HIGHLIGHT_COLOR;

  const normalized = rawColor.toLowerCase();
  const defaultHex = DEFAULT_HIGHLIGHT_COLOR.toLowerCase();

  if (normalized === defaultHex || normalized === "lightgreen") {
    return {
      name: DEFAULT_HIGHLIGHT_COLOR,
      background: DEFAULT_HIGHLIGHT_RGBA,
      border: DEFAULT_HIGHLIGHT_BORDER,
    };
  }

  if (normalized.startsWith("#")) {
    return {
      name: rawColor,
      background: hexToRgba(normalized, 0.45),
      border: rawColor,
    };
  }

  if (normalized.startsWith("rgb")) {
    return {
      name: rawColor,
      background: rawColor,
      border: rawColor,
    };
  }

  const preset = palette[normalized];
  if (preset) {
    return {
      name: normalized,
      background: preset.background,
      border: preset.border,
    };
  }

  return {
    name: rawColor,
    background: DEFAULT_HIGHLIGHT_RGBA,
    border: DEFAULT_HIGHLIGHT_BORDER,
  };
}

// Remove all highlights from all pages
function clearAllHighlights() {
  const allTextLayers = document.querySelectorAll(".textLayer");
  let totalCleared = 0;
  
  allTextLayers.forEach((textLayer) => {
    const highlights = textLayer.querySelectorAll(".note-highlight");
    highlights.forEach((h) => {
      const parent = h.parentNode;
      while (h.firstChild) {
        parent.insertBefore(h.firstChild, h);
      }
      parent.removeChild(h);
      totalCleared++;
    });
  });
  
  if (totalCleared > 0) {
    console.log(`🧹 Cleared ${totalCleared} highlights from all pages`);
  }
}

// Highlight notes on current page
async function highlightNotesOnPage(pageNum) {
  if (!bookNotes || bookNotes.length === 0) {
    console.log(`ℹ️ No annotations to highlight (page ${pageNum})`);
    return;
  }
  console.log(`🎨 Highlighting notes on page ${pageNum}`);
  console.log(`Total bookNotes array length: ${bookNotes.length}`);
  console.log(
    `All bookNotes:`,
    bookNotes.map((n) => ({
      id: n.id,
      page: resolveNotePage(n),
      hasText: !!resolveNoteText(n),
    }))
  );

  ensurePageIcon(pageNum);

  // Get notes for this page
  const pageNotes = bookNotes.filter((note) => resolveNotePage(note) === pageNum);

  if (pageNotes.length === 0) {
    console.log(`❌ No notes found for page ${pageNum}`);
    console.log(`Available pages in bookNotes:`, [
      ...new Set(bookNotes.map((n) => resolveNotePage(n))),
    ]);
    return;
  }

  console.log(`✅ Found ${pageNotes.length} notes for page ${pageNum}`);

  const { textLayer, spans: textSpans } = await waitForTextLayerReady(pageNum, 30, 120);

  if (!textLayer) {
    console.warn(`❌ Text layer not available for page ${pageNum} after waiting`);
    return;
  }

  if (!textSpans || textSpans.length === 0) {
    console.warn(`❌ No text spans found for page ${pageNum} after waiting`);
    console.warn(`Text layer HTML:`, textLayer.innerHTML?.substring(0, 500));
    return;
  }

  console.log(`📚 Text layer ready for page ${pageNum} with ${textSpans.length} spans`);

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
    try {
      console.log(`\n📍 Processing note ${index + 1}/${pageNotes.length}`);

      const rawSelectedText = resolveNoteText(note);
      if (!rawSelectedText) {
        console.log(`Note ${index} has no selected text payload`);
        return;
      }

      // Normalize whitespace in search text (replace multiple spaces/newlines with single space)
      const searchText = rawSelectedText.trim().replace(/\s+/g, " ");
      if (!searchText) {
        console.log(`Note ${index} searchText is empty`);
        return;
      }

      console.log(`Searching for: "${searchText.substring(0, 50)}..."`);
      console.log(`Search text length: ${searchText.length}`);
      console.log(`Using ${textSpans.length} text spans`);

      // Build full text from all spans and track their positions
      // Each span is a line - we need to search across them accounting for line breaks
      let fullPageText = "";
      let normalizedPageText = "";
      const spanPositions = [];

      for (let i = 0; i < textSpans.length; i++) {
        const span = textSpans[i];
        const rawText = span.textContent || "";
        // Normalize whitespace within the line (collapses multiple spaces/newlines to single space)
        const normalizedLine = rawText.replace(/\s+/g, " ").trim();

        const rawStart = fullPageText.length;
        const normalizedStart = normalizedPageText.length;

        // Concatenate raw text (preserves original structure)
        fullPageText += rawText;

        // For normalized text, join lines with a space to match how selectedText likely stores multi-line selections
        if (normalizedLine) {
          if (normalizedPageText.length > 0) {
            // Add space separator between lines
            normalizedPageText += " ";
          }
          normalizedPageText += normalizedLine;
        }

        const rawEnd = fullPageText.length;
        const normalizedEnd = normalizedPageText.length;

        spanPositions.push({
          span: span,
          rawStart,
          rawEnd,
          normalizedStart,
          normalizedEnd,
          rawText,
          normalizedText: normalizedLine,
          spanIndex: i,
        });
      }

      console.log(`Built full page text: ${fullPageText.length} characters`);
      console.log(
        `Normalized text preview: "${normalizedPageText.substring(0, 200)}..."`
      );

      // Search in normalized text
      const textIndex = normalizedPageText.indexOf(searchText);
      console.log(`Text found at normalized index: ${textIndex}`);

      if (textIndex === -1) {
        console.warn(`❌ Text not found: "${searchText.substring(0, 30)}..."`);
        console.log(`Attempting fuzzy match...`);

        // Try fuzzy match - search for first few words
        const searchWords = searchText.split(" ").filter((w) => w.length > 2);
        if (searchWords.length > 0) {
          const fuzzySearch = searchWords
            .slice(0, Math.min(2, searchWords.length))
            .join(" ");
          const fuzzyIndex = normalizedPageText.indexOf(fuzzySearch);
          if (fuzzyIndex !== -1) {
            console.log(`✅ Found fuzzy match at index: ${fuzzyIndex}`);
            // Use fuzzy match - continue with highlighting
            highlightTextAcrossSpans(
              spanPositions,
              fuzzyIndex,
              fuzzySearch.length,
              note,
              pageNum,
              index,
              textLayer
            );
          } else {
            console.log(`❌ No fuzzy match found`);
          }
        }
        return;
      }

      // Exact match found - highlight it
      highlightTextAcrossSpans(
        spanPositions,
        textIndex,
        searchText.length,
        note,
        pageNum,
        index,
        textLayer
      );
    } catch (error) {
      console.error(`❌ Error processing note ${index}:`, error);
      console.error(`   Note data:`, note);
      console.error(`   Stack trace:`, error.stack);
    }
  });
}

// Helper function to highlight text across multiple line spans
function highlightTextAcrossSpans(
  spanPositions,
  matchIndex,
  matchLength,
  note,
  pageNum,
  noteIndex,
  textLayer
) {
  const matchEnd = matchIndex + matchLength;
  const highlightStyle = resolveHighlightStyle(note);

  console.log(
    `🎯 Highlighting from normalized index ${matchIndex} to ${matchEnd} (length: ${matchLength})`
  );

  // Find the starting span (where matchIndex falls)
  let startSpanIndex = -1;
  let endSpanIndex = -1;

  for (let i = 0; i < spanPositions.length; i++) {
    const pos = spanPositions[i];

    // Check if match starts in this span
    if (matchIndex >= pos.normalizedStart && matchIndex < pos.normalizedEnd) {
      startSpanIndex = i;
    }

    // Check if match ends in this span
    if (matchEnd > pos.normalizedStart && matchEnd <= pos.normalizedEnd) {
      endSpanIndex = i;
    }

    // Check if this span is completely within the match
    if (pos.normalizedStart >= matchIndex && pos.normalizedEnd <= matchEnd) {
      if (startSpanIndex === -1) startSpanIndex = i;
      if (endSpanIndex === -1 || i > endSpanIndex) endSpanIndex = i;
    }
  }

  // If we didn't find exact matches, try to find spans that overlap
  if (startSpanIndex === -1 || endSpanIndex === -1) {
    for (let i = 0; i < spanPositions.length; i++) {
      const pos = spanPositions[i];
      if (matchIndex < pos.normalizedEnd && matchEnd > pos.normalizedStart) {
        if (startSpanIndex === -1) startSpanIndex = i;
        endSpanIndex = i;
      }
    }
  }

  if (startSpanIndex === -1 || endSpanIndex === -1) {
    console.error(
      `❌ Could not find spans for match (start: ${startSpanIndex}, end: ${endSpanIndex})`
    );
    return;
  }

  console.log(
    `📌 Highlight spans ${startSpanIndex} to ${endSpanIndex} (${
      endSpanIndex - startSpanIndex + 1
    } spans)`
  );

  // Create highlight wrapper function
  function createHighlightSpan() {
    const highlightSpan = document.createElement("span");
    highlightSpan.className = "note-highlight";
    highlightSpan.setAttribute("data-note-id", note.id);
    highlightSpan.dataset.color = highlightStyle.name;
    highlightSpan.setAttribute("tabindex", "0");
    highlightSpan.style.setProperty(
      "background-color",
      highlightStyle.background,
      "important"
    );
    highlightSpan.style.setProperty("cursor", "pointer", "important");
    highlightSpan.style.setProperty(
      "border-bottom",
      `2px solid ${highlightStyle.border}`,
      "important"
    );
    highlightSpan.style.setProperty("display", "inline", "important");

    const activateNote = () => {
      try {
        hideSelectionTooltip();
      } catch (err) {
        // ignore tooltip errors
      }
      const selection = window.getSelection();
      if (selection) {
        selection.removeAllRanges();
      }
      sendToFlutter("noteClicked", {
        noteId: note.id,
        page: pageNum,
      });
    };

    const suppressSelection = (event) => {
      event.preventDefault();
      event.stopPropagation();
    };

    const isHighlightOnly = note.source === "highlight";

    highlightSpan.addEventListener("pointerdown", suppressSelection);
    highlightSpan.addEventListener("mousedown", suppressSelection);
    highlightSpan.addEventListener("touchstart", suppressSelection, {
      passive: false,
    });

    if (isHighlightOnly) {
      // For highlights: show delete menu on click (toggle)
      highlightSpan.addEventListener("click", (event) => {
        suppressSelection(event);
        // Toggle delete menu on click
        if (currentDeleteMenu && currentDeleteMenu.dataset.highlightId === note.id) {
          hideHighlightDeleteMenu();
        } else {
          showHighlightDeleteMenu(note, highlightSpan, event);
        }
      });
    } else {
      // For notes: open edit dialog on click
      highlightSpan.addEventListener("click", (event) => {
        suppressSelection(event);
        activateNote();
      });
    }

    highlightSpan.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        suppressSelection(event);
        if (isHighlightOnly) {
          if (currentDeleteMenu && currentDeleteMenu.dataset.highlightId === note.id) {
            hideHighlightDeleteMenu();
          } else {
            showHighlightDeleteMenu(note, highlightSpan, event);
          }
        } else {
          activateNote();
        }
      }
    });
    // No hover tooltips for either highlights or notes

    return highlightSpan;
  }

  // Process each affected span
  try {
    for (let i = startSpanIndex; i <= endSpanIndex; i++) {
      const spanPos = spanPositions[i];
      const span = spanPos.span;
      const textContent = span.textContent || "";

      console.log(
        `  Processing span ${i}: "${textContent.substring(0, 30)}..."`
      );

      if (i === startSpanIndex && i === endSpanIndex) {
        // Match is entirely within one span
        const relativeStart = Math.max(0, matchIndex - spanPos.normalizedStart);
        const relativeEnd = Math.min(
          textContent.length,
          matchEnd - spanPos.normalizedStart
        );

        const beforeText = textContent.substring(0, relativeStart);
        const highlightText = textContent.substring(relativeStart, relativeEnd);
        const afterText = textContent.substring(relativeEnd);

        console.log(
          `  Single span highlight: before="${beforeText}", highlight="${highlightText}", after="${afterText}"`
        );

        if (highlightText.trim()) {
          const highlightSpan = createHighlightSpan();
          highlightSpan.textContent = highlightText;

          span.textContent = "";
          if (beforeText) span.appendChild(document.createTextNode(beforeText));
          span.appendChild(highlightSpan);
          if (afterText) span.appendChild(document.createTextNode(afterText));
        }
      } else if (i === startSpanIndex) {
        // Match starts in this span - highlight from match start to end of span
        const relativeStart = Math.max(0, matchIndex - spanPos.normalizedStart);
        const beforeText = textContent.substring(0, relativeStart);
        const highlightText = textContent.substring(relativeStart);

        console.log(
          `  Start span: highlight="${highlightText.substring(0, 30)}..."`
        );

        if (highlightText.trim()) {
          const highlightSpan = createHighlightSpan();
          highlightSpan.textContent = highlightText;

          span.textContent = "";
          if (beforeText) span.appendChild(document.createTextNode(beforeText));
          span.appendChild(highlightSpan);
        }
      } else if (i === endSpanIndex) {
        // Match ends in this span - highlight from start of span to match end
        const relativeEnd = Math.min(
          textContent.length,
          matchEnd - spanPos.normalizedStart
        );
        const highlightText = textContent.substring(0, relativeEnd);
        const afterText = textContent.substring(relativeEnd);

        console.log(
          `  End span: highlight="${highlightText.substring(0, 30)}..."`
        );

        if (highlightText.trim()) {
          const highlightSpan = createHighlightSpan();
          highlightSpan.textContent = highlightText;

          span.textContent = "";
          span.appendChild(highlightSpan);
          if (afterText) span.appendChild(document.createTextNode(afterText));
        }
      } else {
        // Span is completely within the match - highlight entire span
        console.log(`  Middle span: highlighting entire span`);

        if (textContent.trim()) {
          const highlightSpan = createHighlightSpan();
          highlightSpan.textContent = textContent;
          span.textContent = "";
          span.appendChild(highlightSpan);
        }
      }
    }
  } catch (error) {
    console.error(`❌ Error in highlightTextAcrossSpans:`, error);
    console.error(`   Stack trace:`, error.stack);
  }

  console.log(
    `✅ Highlight applied across ${
      endSpanIndex - startSpanIndex + 1
    } spans for note ${noteIndex}`
  );
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

// Show highlight delete menu on right-click
let currentDeleteMenu = null;

function showHighlightDeleteMenu(note, element, event) {
  hideHighlightDeleteMenu();
  
  const menu = document.createElement("div");
  menu.className = "highlight-delete-menu";
  menu.dataset.highlightId = note.id;
  menu.style.cssText = `
    position: fixed;
    background: white;
    border: 1px solid #ccc;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 10001;
    padding: 4px;
    min-width: 120px;
  `;
  
  const deleteButton = document.createElement("button");
  deleteButton.textContent = "🗑️ Delete Highlight";
  deleteButton.style.cssText = `
    width: 100%;
    padding: 8px 12px;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    font-size: 14px;
    border-radius: 4px;
    transition: background-color 0.2s;
  `;
  deleteButton.addEventListener("mouseenter", () => {
    deleteButton.style.backgroundColor = "#f5f5f5";
  });
  deleteButton.addEventListener("mouseleave", () => {
    deleteButton.style.backgroundColor = "transparent";
  });
  deleteButton.addEventListener("click", (e) => {
    e.stopPropagation();
    sendToFlutter("deleteHighlight", {
      highlightId: note.id,
      page: currentPage,
    });
    hideHighlightDeleteMenu();
  });
  
  menu.appendChild(deleteButton);
  document.body.appendChild(menu);
  
  const rect = event.getBoundingClientRect ? event : element.getBoundingClientRect();
  const x = rect.clientX || rect.left || 0;
  const y = rect.clientY || rect.top || 0;
  
  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;
  
  currentDeleteMenu = menu;
  
  setTimeout(() => {
    const closeOnOutsideClick = (e) => {
      if (!menu.contains(e.target)) {
        hideHighlightDeleteMenu();
        document.removeEventListener("click", closeOnOutsideClick);
      }
    };
    document.addEventListener("click", closeOnOutsideClick);
  }, 100);
}

function hideHighlightDeleteMenu() {
  if (currentDeleteMenu) {
    currentDeleteMenu.remove();
    currentDeleteMenu = null;
  }
}

// Selection tooltip variables
let currentTooltip = null;
let touchStartTime = 0;
let touchStartPos = null;

function setTooltipInteractionActive(active) {
  if (active) {
    isTooltipInteractionActive = true;
    if (tooltipInteractionTimeout) {
      clearTimeout(tooltipInteractionTimeout);
      tooltipInteractionTimeout = null;
    }
  } else {
    if (tooltipInteractionTimeout) {
      clearTimeout(tooltipInteractionTimeout);
    }
    tooltipInteractionTimeout = setTimeout(() => {
      isTooltipInteractionActive = false;
      tooltipInteractionTimeout = null;
    }, 40);
  }
}

function createTooltipButton(icon, label, onClick) {
  const button = document.createElement("button");
  button.className = "selection-tooltip-button";
  button.setAttribute("aria-label", label);
  button.setAttribute("title", label);
  button.innerHTML = icon;
  button.addEventListener("click", onClick);
  button.addEventListener("pointerdown", () => setTooltipInteractionActive(true));
  return button;
}

// Show selection tooltip
function showSelectionTooltip(selection, rect) {
  // Hide existing tooltip
  hideSelectionTooltip();

  if (!selection || !selectedText) {
    return;
  }

  // Create tooltip container
  const tooltip = document.createElement("div");
  tooltip.className = "selection-tooltip";
  tooltip.addEventListener("pointerdown", () => setTooltipInteractionActive(true));
  tooltip.addEventListener("pointerleave", () => setTooltipInteractionActive(false));

  // Highlight button with color picker
  const highlightButton = createTooltipButton("🖍️", "Highlight", () => {
    createHighlight({ color: DEFAULT_HIGHLIGHT_COLOR });
    hideSelectionTooltip();
  });
  tooltip.appendChild(highlightButton);

  // Divider
  const divider1 = document.createElement("div");
  divider1.className = "tooltip-divider";
  tooltip.appendChild(divider1);

  // Note button
  const noteButton = createTooltipButton("📝", "Add Note", () => {
    sendToFlutter("createNoteFromSelection", {
      selectedText: selectedText,
      page: currentPage,
      position: selectedTextPosition,
    });
    hideSelectionTooltip();
  });
  tooltip.appendChild(noteButton);

  // AI button
  const aiButton = createTooltipButton("🤖", "Ask AI", () => {
    sendToFlutter("askAI", {
      selectedText: selectedText,
      page: currentPage,
    });
    hideSelectionTooltip();
  });
  tooltip.appendChild(aiButton);

  // Define button
  const defineButton = createTooltipButton("📖", "Define", () => {
    sendToFlutter("defineWord", {
      selectedText: selectedText,
      page: currentPage,
    });
    hideSelectionTooltip();
  });
  tooltip.appendChild(defineButton);

  // Add to document
  document.body.appendChild(tooltip);

  // Position tooltip
  positionTooltip(tooltip, rect);

  currentTooltip = tooltip;

  // Close tooltip when clicking outside
  setTimeout(() => {
    document.addEventListener(
      "click",
      (e) => {
        if (currentTooltip && !currentTooltip.contains(e.target)) {
          hideSelectionTooltip();
        }
      },
      { once: true }
    );
  }, 100);
}

// Position tooltip near selection
function positionTooltip(tooltip, rect) {
  if (!tooltip || !rect) return;
  
  // Make tooltip visible to measure its actual dimensions
  tooltip.style.visibility = 'hidden';
  tooltip.style.position = 'fixed';
  
  // Wait for next frame to get accurate dimensions
  requestAnimationFrame(() => {
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width || 200;
    const tooltipHeight = tooltipRect.height || 50;
    
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    // Center tooltip horizontally relative to selection
    let left = rect.left + (rect.width / 2) - (tooltipWidth / 2);
    
    // Position above selection by default
    let top = rect.top - tooltipHeight - 10;
    
    // Keep tooltip within viewport horizontally
    if (left < 10) left = 10;
    if (left + tooltipWidth > viewportWidth - 10) {
      left = viewportWidth - tooltipWidth - 10;
    }
    
    // If tooltip would be above viewport, show below selection
    if (top < 10) {
      top = rect.bottom + 10;
    }
    
    // If tooltip would be below viewport, force it above
    if (top + tooltipHeight > viewportHeight - 10) {
      top = rect.top - tooltipHeight - 10;
      // Last resort: show at top of viewport
      if (top < 10) {
        top = 10;
      }
    }
    
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    tooltip.style.visibility = 'visible';
  });
}

// Hide selection tooltip
function hideSelectionTooltip() {
  if (currentTooltip) {
    currentTooltip.remove();
    currentTooltip = null;
  }
  if (tooltipInteractionTimeout) {
    clearTimeout(tooltipInteractionTimeout);
    tooltipInteractionTimeout = null;
  }
  isTooltipInteractionActive = false;
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

    // Mobile long-press support
    document.addEventListener(
      "touchstart",
      (e) => {
        touchStartTime = Date.now();
        if (e.touches && e.touches.length > 0) {
          touchStartPos = {
            x: e.touches[0].clientX,
            y: e.touches[0].clientY,
          };
        }
      },
      { passive: true }
    );

    document.addEventListener(
      "touchend",
      (e) => {
        const touchDuration = Date.now() - touchStartTime;
        const selection = window.getSelection();

        // If text is selected (either from long press or native selection)
        if (selection && selection.toString().trim()) {
          setTimeout(() => {
            const currentSelection = window.getSelection();
            if (currentSelection && currentSelection.toString().trim()) {
              const range = currentSelection.getRangeAt(0);
              const rect = range.getBoundingClientRect();
              showSelectionTooltip(currentSelection, rect);
            }
          }, 150);
        }
      },
      { passive: true }
    );

    // Desktop right-click support (optional enhancement)
    document.addEventListener("contextmenu", (e) => {
      const selection = window.getSelection();
      if (selection && selection.toString().trim()) {
        e.preventDefault(); // Prevent default context menu
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        showSelectionTooltip(selection, rect);
      }
    });
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

      eventBus.on("pagesinit", function () {
        console.log("🧭 pagesinit detected, adding icons to all pages");
        addIconsToAllPages();
      });

      eventBus.on("pagerendered", function (evt) {
        if (evt && typeof evt.pageNumber === "number") {
          ensurePageIcon(evt.pageNumber);
        }
      });
      
      // CRITICAL: Listen for textlayerrendered - this is when text layer is ready
      eventBus.on("textlayerrendered", function (evt) {
        if (evt && typeof evt.pageNumber === "number") {
          console.log(`📝 textLayer rendered for page ${evt.pageNumber}`);
          // Highlight notes for this specific page once its text layer is ready
          if (bookNotes.length > 0) {
            const pageNotes = bookNotes.filter((note) => resolveNotePage(note) === evt.pageNumber);
            if (pageNotes.length > 0) {
              console.log(`🎨 Triggering highlight for page ${evt.pageNumber} after textlayerrendered (${pageNotes.length} notes)`);
              // Small delay to ensure text layer is fully painted
              setTimeout(() => highlightNotesOnPage(evt.pageNumber), 100);
            }
          }
        }
      });

      // Initial page
      currentPage = window.PDFViewerApplication.page || 1;
      pageStartTime = Date.now();
      ensurePageIcon(currentPage);

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
  showSelectionTooltip: showSelectionTooltip,
  hideSelectionTooltip: hideSelectionTooltip,
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
