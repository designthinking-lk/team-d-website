const fallbackReviewData = {
  metadata: {
    source: "sample",
    createdBy: "gesture_review/app.js",
    note: "Replace this with JSON generated from the Aria SDK pipeline."
  },
  summary: [
    { label: "Gesture Score", value: "72%", note: "Moderate support" },
    { label: "Hands Visible", value: "68%", note: "3 improvement moments" },
    { label: "Increased Heart Rate", value: "3", note: "Elevated heart-rate moments" },
    { label: "Good Moments", value: "4", note: "Confident delivery signals" }
  ],
  segments: [
    {
      id: "seg-001",
      start: "00:00",
      end: "00:08",
      parts: [
        { text: "Hello everyone, today I will introduce " },
        {
          text: "our judgement free speaking mentor",
          type: "good",
          title: "Good opening posture",
          label: "Good moment",
          evidence: "Hands were visible and movement was calm during the opening.",
          meaning: "Your body language supported the first impression of the speech.",
          suggestion: "Keep this steady opening style when introducing your main topic."
        },
        { text: "." }
      ]
    },
    {
      id: "seg-002",
      start: "00:09",
      end: "00:17",
      parts: [
        { text: "Many people feel nervous when they have to speak in front of others, especially when " },
        {
          text: "they think they are being judged",
          type: "stress",
          title: "Possible stress signal",
          label: "Increased heart rate",
          evidence: "The PPG signal rose above the session baseline for this section.",
          meaning: "This may indicate a nervous moment while explaining the problem.",
          suggestion: "Pause before this sentence and begin it slightly slower next time."
        },
        { text: "." }
      ]
    },
    {
      id: "seg-003",
      start: "00:18",
      end: "00:31",
      parts: [
        { text: "Our project uses Meta Aria glasses to observe speech delivery signals and provide private feedback after practice." }
      ]
    },
    {
      id: "seg-004",
      start: "00:32",
      end: "00:46",
      parts: [
        { text: "The glasses can help us understand " },
        {
          text: "when the speaker's hands move outside the field of view",
          type: "gesture",
          title: "Gesture could be clearer",
          label: "Gesture improvement",
          evidence: "Aria hand tracking did not detect visible hands for most of this section.",
          meaning: "The audience may not be able to read gestures clearly in this moment.",
          suggestion: "Keep gestures closer to chest level when explaining key ideas."
        },
        { text: "." }
      ]
    },
    {
      id: "seg-005",
      start: "00:47",
      end: "01:02",
      parts: [
        { text: "We also use heart-rate signals to find parts of the speech where the speaker may have felt tense." }
      ]
    },
    {
      id: "seg-006",
      start: "01:03",
      end: "01:16",
      parts: [
        { text: "The goal is not to criticize the speaker, but to show " },
        {
          text: "clear improvement opportunities",
          type: "good",
          title: "Strong delivery moment",
          label: "Good moment",
          evidence: "Hands stayed visible and movement was moderate during this explanation.",
          meaning: "Your gestures supported the message without distracting from it.",
          suggestion: "Use this style for other important points in the speech."
        },
        { text: "." }
      ]
    },
    {
      id: "seg-007",
      start: "01:17",
      end: "01:29",
      parts: [
        {
          text: "In future work, we want the mentor to give more personalized suggestions",
          type: "gesture",
          title: "Low gesture activity",
          label: "Gesture improvement",
          evidence: "Aria hand tracking showed little hand movement across this section.",
          meaning: "This section may feel less expressive because the gesture activity was low.",
          suggestion: "Add one open-hand gesture when introducing future work or conclusions."
        },
        { text: "." }
      ]
    },
    {
      id: "seg-008",
      start: "01:30",
      end: "01:42",
      parts: [
        { text: "Thank you for listening, and I am happy to answer your questions." },
        {
          text: " ",
          type: "stress",
          title: "Possible closing tension",
          label: "Increased heart rate",
          evidence: "The PPG signal stayed elevated near the closing.",
          meaning: "Question transitions can create pressure, so this signal is worth reviewing.",
          suggestion: "Finish with a slower final sentence and one breath before inviting questions."
        }
      ]
    }
  ]
};

let reviewData = fallbackReviewData;
let activeFillerMode = false;
let activeFillerButton = null;

const transcriptList = document.querySelector("#transcriptList");
const emptyState = document.querySelector("#emptyState");
const detailsContent = document.querySelector("#detailsContent");
const detailBadge = document.querySelector("#detailBadge");
const detailTime = document.querySelector("#detailTime");
const detailTitle = document.querySelector("#detailTitle");
const detailEvidence = document.querySelector("#detailEvidence");
const detailMeaning = document.querySelector("#detailMeaning");
const detailSuggestion = document.querySelector("#detailSuggestion");
const exportButton = document.querySelector("#exportButton");
const reportInput = document.querySelector("#reportInput");
const dataSource = document.querySelector("#dataSource");
const summaryGrid = document.querySelector("#summaryGrid");
const metadataStrip = document.querySelector("#metadataStrip");
const eyeReport = document.querySelector("#eyeReport");
const eyeMetrics = document.querySelector("#eyeMetrics");
const eyeEmpty = document.querySelector("#eyeEmpty");
const eyeHeatmapImage = document.querySelector("#eyeHeatmapImage");
const eyeTimelineImage = document.querySelector("#eyeTimelineImage");
const eyeAudienceMap = document.querySelector("#eyeAudienceMap");

function renderSummary(summary) {
  summaryGrid.innerHTML = "";

  summary.forEach((item) => {
    const card = document.createElement("article");
    card.className = "summary-card";

    const label = document.createElement("span");
    label.className = "summary-label";
    label.textContent = item.label;

    const value = document.createElement("strong");
    value.textContent = item.value;

    const note = document.createElement("span");
    note.className = "summary-note";
    note.textContent = item.note;

    card.append(label, value, note);
    summaryGrid.append(card);
  });
}

function renderMetadata(metadata) {
  const duration = metadata.duration_s || metadata.voice_duration_s;
  const fillerReport = metadata.filler_report;
  const items = [
    duration ? { label: "Duration", value: formatDuration(duration) } : null,
    fillerReport ? {
      label: "Fillers",
      value: String(fillerReport.filler_count || 0),
      action: (button) => showFillerDetails(fillerReport, button)
    } : null
  ].filter(Boolean);

  metadataStrip.innerHTML = "";

  if (!items.length) {
    metadataStrip.classList.add("hidden");
    return;
  }

  metadataStrip.classList.remove("hidden");
  items.forEach((metadataItem) => {
    const item = document.createElement(metadataItem.action ? "button" : "span");
    if (metadataItem.action) {
      item.type = "button";
      item.addEventListener("click", (event) => metadataItem.action(event.currentTarget));
    }
    item.innerHTML = `<strong>${metadataItem.label}</strong> ${metadataItem.value}`;
    metadataStrip.append(item);
  });
}

function formatDuration(seconds) {
  const totalSeconds = Math.round(Number(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (!minutes) {
    return `${remainingSeconds}s`;
  }
  return `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`;
}

function formatRange(range) {
  if (!range) {
    return "--";
  }

  return `${range.min} to ${range.max} deg`;
}

function renderEyeMetrics(report) {
  const metrics = [
    report.yaw_range_deg ? ["Horizontal range", formatRange(report.yaw_range_deg)] : null,
    report.pitch_range_deg ? ["Vertical range", formatRange(report.pitch_range_deg)] : null,
    report.average_fixation_s ? ["Avg. fixation", `${report.average_fixation_s}s`] : null
  ].filter(Boolean);

  eyeMetrics.innerHTML = "";
  metrics.forEach(([label, value]) => {
    const item = document.createElement("article");
    item.className = "eye-metric";
    item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    eyeMetrics.append(item);
  });
}

function zoneClass(zone) {
  return zone.toLowerCase().replace("/", "-").replace(/\s+/g, "-");
}

function renderAudienceMap(report) {
  const zones = report.zone_percentages || {};
  const zoneOrder = [
    ["Left Audience", "Left"],
    ["Center Audience", "Center"],
    ["Right Audience", "Right"],
    ["Notes/Floor", "Floor/Notes"]
  ];

  eyeAudienceMap.innerHTML = "";
  zoneOrder.forEach(([zone, label]) => {
    const pct = zones[zone] || 0;
    const section = document.createElement("article");
    section.className = `audience-zone ${zoneClass(zone)}`;
    section.style.setProperty("--zone-strength", `${Math.max(0.12, pct / 100)}`);
    section.innerHTML = `
      <span>${label}</span>
      <strong>${pct}%</strong>
      <i><b style="width: ${Math.max(0, Math.min(100, pct))}%"></b></i>
    `;
    eyeAudienceMap.append(section);
  });
}

function setEyeImage(image, src) {
  if (!src) {
    image.classList.add("hidden");
    image.removeAttribute("src");
    return;
  }

  image.classList.remove("hidden");
  image.src = src;
}

function formatWordList(items) {
  if (!items || !items.length) {
    return "None detected.";
  }

  return items.map((item) => `${item.text} (${item.count})`).join(", ");
}

function showFillerDetails(report, activeButton = null) {
  if (activeFillerMode && activeFillerButton === activeButton) {
    activeFillerMode = false;
    activeFillerButton = null;
    activeButton.classList.remove("active");
    renderTranscript();
    resetDetails();
    return;
  }

  activeFillerMode = true;
  if (activeFillerButton) {
    activeFillerButton.classList.remove("active");
  }
  activeFillerButton = activeButton;
  if (activeFillerButton) {
    activeFillerButton.classList.add("active");
  }
  renderTranscript();

  document.querySelectorAll(".highlight.active").forEach((button) => {
    button.classList.remove("active");
  });

  emptyState.classList.add("hidden");
  detailsContent.classList.remove("hidden");

  detailBadge.className = "detail-badge filler";
  detailBadge.textContent = "Fillers";
  detailTime.textContent = "Whole speech";
  detailTitle.textContent = "Filler and repeated words";
  detailEvidence.textContent = [
    `Filler words: ${formatWordList(report.filler_words)}`,
    `Repeated words or phrases: ${formatWordList(report.repeated_words)}`
  ].join(" ");
  detailMeaning.textContent = `${report.filler_count || 0} filler words and ${report.repeated_count || 0} repeated words or phrases were detected, about ${report.per_minute || 0} per minute.`;
  detailSuggestion.textContent = "When you notice these patterns, pause briefly instead of filling the silence. Short pauses usually sound more confident than repeated words.";
}

function renderEyeReport(metadata) {
  const report = metadata.eye_tracking_report || {};
  const images = metadata.eye_tracking_images || {};
  const heatmapImage = images.heatmap || metadata.eye_tracking_image;
  const timelineImage = images.timeline;
  const hasReport = Boolean(heatmapImage || timelineImage || Object.keys(report).length);

  if (!hasReport) {
    eyeReport.classList.remove("hidden");
    eyeEmpty.classList.remove("hidden");
    setEyeImage(eyeHeatmapImage, null);
    setEyeImage(eyeTimelineImage, null);
    eyeMetrics.innerHTML = "";
    eyeAudienceMap.innerHTML = "";
    return;
  }

  eyeReport.classList.remove("hidden");
  eyeEmpty.classList.add("hidden");
  renderEyeMetrics(report);
  renderAudienceMap(report);
  setEyeImage(eyeHeatmapImage, heatmapImage);
  setEyeImage(eyeTimelineImage, timelineImage);
}

function renderTranscript() {
  transcriptList.innerHTML = "";

  reviewData.segments.forEach((segment) => {
    const row = document.createElement("article");
    row.className = "transcript-row";

    const timestamp = document.createElement("span");
    timestamp.className = "timestamp";
    timestamp.textContent = `${segment.start} - ${segment.end}`;

    const text = document.createElement("p");
    text.className = "transcript-text";

    if (activeFillerMode) {
      renderFillerTranscriptSegment(segment, text);
      row.append(timestamp, text);
      transcriptList.append(row);
      return;
    }

    segment.parts.forEach((part, index) => {
      if (!part.type) {
        text.append(document.createTextNode(part.text));
        return;
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = `highlight ${part.type}`;
      button.textContent = part.text.trim() || part.label;
      button.dataset.segmentId = segment.id;
      button.dataset.partIndex = String(index);
      button.addEventListener("click", () => showDetails(segment, part, button));
      text.append(button);

      if (part.text.endsWith(" ")) {
        text.append(document.createTextNode(" "));
      }
    });

    row.append(timestamp, text);
    transcriptList.append(row);
  });
}

function fillerOccurrencesBySegment(segmentId) {
  const report = reviewData.metadata.filler_report || {};
  const occurrences = [
    ...((report.occurrences && report.occurrences.fillers) || []),
    ...((report.occurrences && report.occurrences.repeats) || [])
  ];

  return occurrences
    .filter((occurrence) => occurrence.segment_id === segmentId)
    .sort((a, b) => a.index - b.index);
}

function renderFillerTranscriptSegment(segment, textElement) {
  const words = segment.words || [];
  const occurrences = fillerOccurrencesBySegment(segment.id);
  const occurrenceByIndex = new Map();
  occurrences.forEach((occurrence) => {
    occurrenceByIndex.set(occurrence.index, occurrence);
  });

  if (!words.length) {
    textElement.append(document.createTextNode(
      segment.parts.map((part) => part.text).join("")
    ));
    return;
  }

  let index = 0;
  while (index < words.length) {
    const occurrence = occurrenceByIndex.get(index);
    if (!occurrence) {
      textElement.append(document.createTextNode(`${words[index].text} `));
      index += 1;
      continue;
    }

    const wordCount = occurrence.word_count || 1;
    const highlightedWords = words.slice(index, index + wordCount);
    const button = document.createElement("button");
    const type = occurrence.kind === "repeat" ? "repeat" : "filler";
    const label = type === "repeat" ? "Repeated words" : "Filler word";
    const phrase = highlightedWords.map((word) => word.text).join(" ");

    button.type = "button";
    button.className = `highlight ${type}`;
    button.textContent = phrase;
    button.addEventListener("click", () => showDetails(segment, {
      type,
      label,
      title: label,
      evidence: `"${phrase}" was detected in this part of the transcript.`,
      meaning: type === "repeat"
        ? "Repeating the same word or phrase can make the idea sound less planned."
        : "Filler words can make the pause sound less intentional.",
      suggestion: "Try replacing this with a short silent pause before continuing."
    }, button));
    textElement.append(button);
    textElement.append(document.createTextNode(" "));
    index += wordCount;
  }
}

function showDetails(segment, part, activeButton) {
  if (activeFillerButton && activeButton.classList.contains("highlight") && !["filler", "repeat"].includes(part.type)) {
    activeFillerButton.classList.remove("active");
    activeFillerButton = null;
    activeFillerMode = false;
  }

  document.querySelectorAll(".highlight.active").forEach((button) => {
    button.classList.remove("active");
  });
  activeButton.classList.add("active");

  emptyState.classList.add("hidden");
  detailsContent.classList.remove("hidden");

  detailBadge.className = `detail-badge ${part.type}`;
  detailBadge.textContent = part.label;
  detailTime.textContent = `${segment.start} - ${segment.end}`;
  detailTitle.textContent = part.title;
  detailEvidence.textContent = part.evidence;
  detailMeaning.textContent = part.meaning;
  detailSuggestion.textContent = part.suggestion;
}

function resetDetails() {
  emptyState.classList.remove("hidden");
  detailsContent.classList.add("hidden");
}

function setData(nextData, sourceLabel) {
  reviewData = normalizeReviewData(nextData);
  activeFillerMode = false;
  activeFillerButton = null;
  renderSummary(reviewData.summary);
  renderMetadata(reviewData.metadata);
  renderEyeReport(reviewData.metadata);
  renderTranscript();
  resetDetails();
  dataSource.textContent = sourceLabel;
}

function normalizeReviewData(data) {
  if (!data || !Array.isArray(data.segments)) {
    throw new Error("Review JSON must include a segments array.");
  }

  return {
    metadata: data.metadata || {},
    summary: data.summary || buildSummaryFromSegments(data.segments),
    segments: data.segments
  };
}

function buildSummaryFromSegments(segments) {
  const highlightedParts = segments.flatMap((segment) =>
    segment.parts.filter((part) => part.type)
  );
  const stressCount = highlightedParts.filter((part) => part.type === "stress").length;
  const gestureCount = highlightedParts.filter((part) => part.type === "gesture").length;
  const eyeCount = highlightedParts.filter((part) => part.type === "eye").length;
  const voiceCount = highlightedParts.filter((part) => part.type === "voice").length;
  const goodCount = highlightedParts.filter((part) => part.type === "good").length;

  return [
    { label: "Gesture Score", value: "--", note: "Generated from SDK events" },
    { label: "Gesture Issues", value: String(gestureCount), note: "Hand tracking sections" },
    { label: "Eye Contact", value: String(eyeCount), note: "Gaze and audience coverage" },
    { label: "Increased Heart Rate", value: String(stressCount), note: "Elevated heart-rate moments" },
    { label: "Vocal Notes", value: String(voiceCount), note: "Pace or tone variation" },
    { label: "Good Moments", value: String(goodCount), note: "Confident delivery signals" }
  ];
}

function buildReportText() {
  const highlights = reviewData.segments.flatMap((segment) =>
    segment.parts
      .filter((part) => part.type)
      .map((part) => [
        `${segment.start} - ${segment.end}`,
        part.label,
        part.title,
        `Evidence: ${part.evidence}`,
        `Meaning: ${part.meaning}`,
        `Suggestion: ${part.suggestion}`
      ].join("\n"))
  );

  const summary = reviewData.summary.map((item) =>
    `${item.label}: ${item.value} (${item.note})`
  );

  return [
    "EloQ Post Speech Review",
    "",
    "Summary",
    summary.join("\n"),
    "",
    "Detailed Feedback",
    highlights.join("\n\n")
  ].join("\n");
}

reportInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];

  if (!file) {
    return;
  }

  try {
    const data = JSON.parse(await file.text());
    setData(data, file.name);
  } catch (error) {
    alert(`Could not load review JSON: ${error.message}`);
  }
});

exportButton.addEventListener("click", async () => {
  const report = buildReportText();

  try {
    await navigator.clipboard.writeText(report);
    exportButton.textContent = "Copied";
    window.setTimeout(() => {
      exportButton.textContent = "Export Report";
    }, 1400);
  } catch {
    alert(report);
  }
});

const initialData = window.generatedReviewData || fallbackReviewData;
const initialSource = window.generatedReviewData
  ? "Generated CSV report"
  : "Built-in sample data";

setData(initialData, initialSource);
