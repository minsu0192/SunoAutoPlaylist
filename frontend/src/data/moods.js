// ─────────────────────────────────────────────────────────────
// 핵심 무드 데이터베이스
// 이미지 프롬프트는 [규칙 #1]에 따라 no-face suffix를 강제 삽입
// ─────────────────────────────────────────────────────────────

const NO_FACE_SUFFIX = ", viewed strictly from the back, no face visible";
const CHANNEL_TAGS = ["#SeoulDiary", "#KoreanPlaylist", "#AIMusic", "#수노AI"];

export const MOODS = [
  {
    id: "indie",
    emoji: "🌙",
    korName: "트렌디 감성 & 인디 팝",
    engName: "Trendy Indie & Band",
    season: "사계절",
    color: "#7c3aed",

    sunoPrompt:
      "dreamy indie pop, groovy bassline, soft male vocal, wavy synthesizer, atmospheric, reverbed electric guitar, rhythmic band sound",

    imagePrompt:
      "A person standing by a large window looking at the glowing city night sky, neon blue and purple reflections, lofi anime aesthetic, 16:9" +
      NO_FACE_SUFFIX,

    descriptionBody:
      "A late-night drive through the city that never sleeps.\n" +
      "The kind of music that makes the streetlights blur and your thoughts wander.\n" +
      "Dreamy indie soundscapes for souls who feel everything a little too deeply.\n" +
      "Turn it up. Let the night carry you.",

    tags: ["#인디팝", "#드라이브", "#새벽감성", "#신스팝", "#밴드음악", ...CHANNEL_TAGS],

    // 제미나이 트렌드 반영: 트렌딩 키워드 & 롱폼 추천
    trendKeywords: ["lofi aesthetic", "K-indie", "night drive"],
    recommendedLength: "1시간 30분 ~ 2시간",

    shortsHook:
      "✨ 새벽 감성이 필요한 밤... 이 플레이리스트 틀어놔 🌙\nFull playlist in bio 🎵",

    pinnedComment:
      "💬 어떤 무드에서 듣고 있나요? 새벽 드라이브? 혼자만의 시간?\n댓글로 알려주세요 🌙 #SeoulDiary",
  },

  {
    id: "seasonal",
    emoji: "🍂",
    korName: "시즈널 & 기대 심리",
    engName: "Seasonal & Anticipation",
    season: "겨울 / 연말",
    color: "#f59e0b",

    sunoPrompt:
      "warm acoustic pop, gentle piano, cozy holiday vibe, hopeful melody, soft acoustic guitar, comforting, anticipating, cheerful",

    imagePrompt:
      "Someone sitting on a cozy rug in a warmly lit room with string lights, looking out the window at falling snow, warm orange and brown tones, 16:9" +
      NO_FACE_SUFFIX,

    descriptionBody:
      "The year is winding down, but your heart is wide open.\n" +
      "A playlist for quiet evenings, warm drinks, and hopeful thoughts.\n" +
      "Let the season wrap around you like a favorite blanket.\n" +
      "Here's to the moments that made it all worth it.",

    tags: ["#연말플레이리스트", "#휴식", "#어쿠스틱", "#희망찬", "#크리스마스감성", ...CHANNEL_TAGS],

    trendKeywords: ["cozy winter", "year-end vibes", "holiday playlist"],
    recommendedLength: "1시간 ~ 1시간 30분",

    shortsHook:
      "🍂 연말 감성 충전 완료 ✨\n따뜻한 음악으로 마무리하는 12월 🎶\nFull playlist in bio",

    pinnedComment:
      "💬 올해 가장 기억에 남는 순간은 무엇인가요?\n댓글로 나눠요 🍂 #SeoulDiary",
  },

  {
    id: "lofi",
    emoji: "☕",
    korName: "로파이 & 작업용 BGM",
    engName: "Lo-Fi & Focus",
    season: "사계절",
    color: "#10b981",

    sunoPrompt:
      "lofi hip hop, chill beats, vinyl crackle, muffled drum loop, warm electric piano, study background music, instrumental, no vocals",

    imagePrompt:
      "A person typing on a laptop at a desk cluttered with coffee cups and books, late night study session, cyberpunk city outside the window, 16:9" +
      NO_FACE_SUFFIX,

    descriptionBody:
      "Your productivity playlist, engineered for deep focus.\n" +
      "Vinyl warmth, muffled beats, and zero distractions.\n" +
      "Whether you're coding, designing, or just thinking — this one's for you.\n" +
      "Stay in the zone. Ship it.",

    tags: ["#노동요", "#로파이", "#코딩", "#집중BGM", "#공부음악", "#lofi", ...CHANNEL_TAGS],

    trendKeywords: ["study with me", "lofi beats", "coding music"],
    recommendedLength: "2시간 ~ 3시간",

    shortsHook:
      "☕ 집중이 안 될 때 이 플레이리스트 틀어봐 🎧\n공부, 코딩, 야근 다 가능\nFull playlist in bio",

    pinnedComment:
      "💬 지금 뭐 하면서 듣고 있어요? 공부? 코딩? 야근?\n댓글로 알려주세요 ☕ #SeoulDiary",
  },
];
