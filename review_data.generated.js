window.generatedReviewData = {
  "metadata": {
    "source": "split_csv_features",
    "hand_csv": "data/processed/vrs_csv/hand_gesture/hand_gesture1.csv",
    "ppg_csv": "data/processed/vrs_csv/ppg/ppg1.csv",
    "voice_csv": "data/processed/vrs_csv/voice/voice1.csv",
    "eye_csv": "data/processed/vrs_csv/eye_tracking/eye_tracking1.csv",
    "transcript_file": "data/processed/transcript_openai.json",
    "hand_sample_count": 1097,
    "ppg_sample_count": 4698,
    "eye_sample_count": 872,
    "voice_sample_count": 4679680,
    "voice_row_count": 1828,
    "duration_s": 36.59,
    "voice_duration_s": 36.54,
    "baseline_seconds": 10,
    "confidence_threshold": 0.5,
    "ppg_spike_threshold": 5000.0,
    "ppg_variability_threshold": null,
    "audio_file": "data/processed/voice_mono16k.wav",
    "fast_wpm_threshold": 175,
    "slow_wpm_threshold": 95,
    "min_pitch_std_hz": 18,
    "min_volume_std_db": 3.0,
    "eye_tracking_image": "data/processed/eye_tracking_report_heatmap.png",
    "eye_tracking_images": {
      "heatmap": "data/processed/eye_tracking_report_heatmap.png",
      "timeline": "data/processed/eye_tracking_report_timeline.png"
    },
    "eye_tracking_report": {
      "image_path": "data/processed/eye_tracking_report_heatmap.png",
      "images": {
        "heatmap": "data/processed/eye_tracking_report_heatmap.png",
        "timeline": "data/processed/eye_tracking_report_timeline.png"
      },
      "duration_s": 36.53,
      "valid_sample_count": 872,
      "yaw_range_deg": {
        "min": -34.4,
        "max": 34.5,
        "span": 69.0
      },
      "pitch_range_deg": {
        "min": -36.8,
        "max": 4.9,
        "span": 41.7
      },
      "zone_percentages": {
        "Left Audience": 4.2,
        "Center Audience": 67.5,
        "Right Audience": 5.8,
        "Notes/Floor": 22.4
      },
      "average_fixation_s": 0.26
    },
    "filler_report": {
      "total_count": 1,
      "filler_count": 1,
      "repeated_count": 0,
      "per_minute": 1.6,
      "filler_words": [
        {
          "text": "so",
          "count": 1
        }
      ],
      "repeated_words": [],
      "occurrences": {
        "fillers": [
          {
            "text": "So",
            "clean": "so",
            "segment_id": "speech-002",
            "segment_start": 18.94,
            "segment_end": 29.92,
            "start": 22.98,
            "end": 23.22,
            "index": 10,
            "kind": "filler",
            "word_count": 1
          }
        ],
        "repeats": []
      }
    }
  },
  "summary": [
    {
      "label": "Gesture Score",
      "value": "100%",
      "note": "Estimated from Aria hand tracking"
    },
    {
      "label": "Gesture Issues",
      "value": "0",
      "note": "Hands or movement sections"
    },
    {
      "label": "Eye Contact",
      "value": "67.5%",
      "note": "Mostly center audience"
    },
    {
      "label": "Increased Heart Rate",
      "value": "0",
      "note": "Elevated heart-rate moments"
    },
    {
      "label": "Vocal Notes",
      "value": "1",
      "note": "Pace or tone variation"
    },
    {
      "label": "Good Moments",
      "value": "3",
      "note": "Confident delivery signals"
    }
  ],
  "segments": [
    {
      "id": "speech-001",
      "start": "00:13",
      "end": "00:18",
      "words": [
        {
          "text": "Raise",
          "start": 12.62,
          "end": 13.18
        },
        {
          "text": "your",
          "start": 13.18,
          "end": 13.74
        },
        {
          "text": "hand",
          "start": 13.74,
          "end": 14.06
        },
        {
          "text": "if",
          "start": 14.06,
          "end": 14.28
        },
        {
          "text": "you",
          "start": 14.28,
          "end": 14.5
        },
        {
          "text": "ever",
          "start": 14.5,
          "end": 14.78
        },
        {
          "text": "get",
          "start": 14.78,
          "end": 15.0
        },
        {
          "text": "scared",
          "start": 15.0,
          "end": 15.3
        },
        {
          "text": "when",
          "start": 15.3,
          "end": 15.54
        },
        {
          "text": "you're",
          "start": 15.54,
          "end": 16.02
        },
        {
          "text": "speaking",
          "start": 16.02,
          "end": 16.38
        },
        {
          "text": "in",
          "start": 16.38,
          "end": 16.6
        },
        {
          "text": "front",
          "start": 16.6,
          "end": 16.74
        },
        {
          "text": "of",
          "start": 16.74,
          "end": 16.88
        },
        {
          "text": "a",
          "start": 16.88,
          "end": 17.04
        },
        {
          "text": "real",
          "start": 17.04,
          "end": 17.3
        },
        {
          "text": "audience",
          "start": 17.3,
          "end": 17.7
        }
      ],
      "parts": [
        {
          "highlight_start_s": 14.264,
          "highlight_end_s": 16.064,
          "event_time_s": 15.165,
          "text": "Raise your hand",
          "type": "good",
          "title": "Good gesture support",
          "label": "Good moment",
          "evidence": "Hands were visible in 100% of Aria hand tracking samples.",
          "meaning": "Your gestures were available to the audience and supported your delivery.",
          "suggestion": "Keep this gesture range for important points."
        },
        {
          "highlight_start_s": 13.96,
          "highlight_end_s": 16.36,
          "event_time_s": 15.16,
          "type": "voice",
          "title": "Speaking pace was fast",
          "label": "Vocal delivery",
          "evidence": "This section was about 201 words per minute.",
          "meaning": "A fast pace can make details harder for the audience to absorb.",
          "suggestion": "Add a short pause after the key phrase and slow the next sentence slightly.",
          "text": "if you ever get scared when you're speaking"
        },
        {
          "text": "in front of a real audience"
        }
      ]
    },
    {
      "id": "speech-002",
      "start": "00:19",
      "end": "00:30",
      "words": [
        {
          "text": "Well",
          "start": 18.94,
          "end": 19.16
        },
        {
          "text": "you're",
          "start": 19.44,
          "end": 19.64
        },
        {
          "text": "not",
          "start": 19.64,
          "end": 19.98
        },
        {
          "text": "alone",
          "start": 19.98,
          "end": 20.08
        },
        {
          "text": "Many",
          "start": 20.86,
          "end": 20.96
        },
        {
          "text": "of",
          "start": 20.96,
          "end": 21.24
        },
        {
          "text": "us",
          "start": 21.24,
          "end": 21.36
        },
        {
          "text": "have",
          "start": 21.36,
          "end": 21.6
        },
        {
          "text": "that",
          "start": 21.6,
          "end": 21.84
        },
        {
          "text": "fear",
          "start": 21.84,
          "end": 22.1
        },
        {
          "text": "So",
          "start": 22.98,
          "end": 23.22
        },
        {
          "text": "we",
          "start": 23.22,
          "end": 23.74
        },
        {
          "text": "are",
          "start": 23.74,
          "end": 23.94
        },
        {
          "text": "practicing",
          "start": 23.94,
          "end": 24.32
        },
        {
          "text": "alone",
          "start": 24.32,
          "end": 24.76
        },
        {
          "text": "We",
          "start": 27.9,
          "end": 28.46
        },
        {
          "text": "use",
          "start": 28.46,
          "end": 28.86
        },
        {
          "text": "the",
          "start": 28.86,
          "end": 29.92
        }
      ],
      "parts": [
        {
          "text": "Well you're not alone Many of us have that fear So we "
        },
        {
          "highlight_start_s": 23.532,
          "highlight_end_s": 25.331,
          "event_time_s": 24.431,
          "text": "are practicing alone",
          "type": "good",
          "title": "Good gesture support",
          "label": "Good moment",
          "evidence": "Hands were visible in 100% of Aria hand tracking samples.",
          "meaning": "Your gestures were available to the audience and supported your delivery.",
          "suggestion": "Keep this gesture range for important points."
        },
        {
          "text": "We use the"
        }
      ]
    },
    {
      "id": "speech-003",
      "start": "00:30",
      "end": "00:34",
      "words": [
        {
          "text": "words",
          "start": 29.92,
          "end": 31.12
        },
        {
          "text": "You",
          "start": 31.12,
          "end": 31.48
        },
        {
          "text": "don't",
          "start": 31.48,
          "end": 31.68
        },
        {
          "text": "know",
          "start": 31.68,
          "end": 31.8
        },
        {
          "text": "your",
          "start": 31.8,
          "end": 32.08
        },
        {
          "text": "filler",
          "start": 32.08,
          "end": 32.34
        },
        {
          "text": "words",
          "start": 32.34,
          "end": 33.08
        },
        {
          "text": "the",
          "start": 33.6,
          "end": 33.7
        },
        {
          "text": "gestures",
          "start": 33.7,
          "end": 34.24
        }
      ],
      "parts": [
        {
          "text": "words "
        },
        {
          "highlight_start_s": 31.182,
          "highlight_end_s": 32.982,
          "event_time_s": 32.082,
          "text": "You don't know your filler words",
          "type": "good",
          "title": "Good gesture support",
          "label": "Good moment",
          "evidence": "Hands were visible in 100% of Aria hand tracking samples.",
          "meaning": "Your gestures were available to the audience and supported your delivery.",
          "suggestion": "Keep this gesture range for important points."
        },
        {
          "text": "the gestures"
        }
      ]
    }
  ]
};
