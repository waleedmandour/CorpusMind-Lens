// String externalization from day one (§13: i18n) — EN + AR with RTL mirroring.
export type Lang = "en" | "ar";

const en = {
  app: "CorpusMind Lens",
  nav: {
    overview: "Overview",
    imageSets: "Image Sets",
    workbench: "Vision Workbench",
    assistant: "Assistant",
    settings: "Settings",
  },
  common: {
    loading: "Loading…",
    save: "Save",
    delete: "Delete",
    create: "Create",
    upload: "Upload images",
    cancel: "Cancel",
    retry: "Retry",
    ready: "Ready",
    processing: "Processing",
    error: "Error",
    pending: "Pending",
    image: "Image",
    images: "images",
    engine: "Engine",
    version: "Version",
  },
  overview: {
    title: "Welcome to CorpusMind Lens",
    intro:
      "Turn sets of images into publication-ready, statistically grounded, framework-lensed discourse analysis — entirely local-first.",
    projects: "Projects",
    newProject: "New project",
    createSet: "New image set",
    provenance: "Provenance / sampling notes",
    stats: "Set statistics",
  },
  workbench: {
    tabOverview: "Overview",
    tabSet: "Image Set",
    tabMeasures: "Measures",
    tabAnalysis: "Vision Analysis",
    dimension: "Dimension",
    frequency: "Frequency profile",
    diversity: "Diversity battery",
    ngrams: "Sequence n-grams (reading order)",
    dispersion: "Dispersion",
    keyness: "Keyness (vs reference set)",
    kwic: "Visual KWIC",
    run: "Run",
    evidence: "Evidence",
    ungroundedFlag: "ungrounded",
  },
  assistant: {
    placeholder: "Ask about this image set… e.g. “compare these two campaigns' compositional patterns”",
    ask: "Ask",
    grounded: "grounded",
    toolsUsed: "Tools used",
    disclaimer:
      "Every claim resolves to a tool call below or is flagged [ungrounded]. Interpretive claims are framework-lensed hypotheses.",
  },
  settings: {
    aiProviders: "AI providers",
    ethics: "Ethics & consent",
    companion: "Companion Mode",
    appearance: "Appearance",
    language: "Language",
    facial: "Facial & body analysis",
    facialNote:
      "Opt-in, off by default. Descriptive cues only — never identity recognition. GPS is never extracted, under any setting.",
    companionNote:
      "Optional, versioned HTTP integration with a running CorpusMind (Text) engine. Never required for any Lens feature.",
    cloud: "Cloud AI",
    cloudNote: "Off by default. When active, an indicator is always visible.",
    theme: "Theme",
  },
};

const ar: typeof en = {
  app: "كوربس مايند لِنس",
  nav: {
    overview: "نظرة عامة",
    imageSets: "مجموعات الصور",
    workbench: "منضدة الرؤية",
    assistant: "المساعد",
    settings: "الإعدادات",
  },
  common: {
    loading: "جارٍ التحميل…",
    save: "حفظ",
    delete: "حذف",
    create: "إنشاء",
    upload: "رفع الصور",
    cancel: "إلغاء",
    retry: "إعادة المحاولة",
    ready: "جاهزة",
    processing: "قيد المعالجة",
    error: "خطأ",
    pending: "بالانتظار",
    image: "صورة",
    images: "صور",
    engine: "المحرك",
    version: "الإصدار",
  },
  overview: {
    title: "مرحبًا بك في كوربس مايند لِنس",
    intro:
      "حوِّل مجموعات الصور إلى تحليل خطابي مؤطَّر نظريًا ومدعوم إحصائيًا وجاهز للنشر — بخصوصية محلية كاملة.",
    projects: "المشاريع",
    newProject: "مشروع جديد",
    createSet: "مجموعة صور جديدة",
    provenance: "ملاحظات المصدر والمعاينة",
    stats: "إحصاءات المجموعة",
  },
  workbench: {
    tabOverview: "نظرة عامة",
    tabSet: "المجموعة",
    tabMeasures: "القياسات",
    tabAnalysis: "تحليل الرؤية",
    dimension: "البُعد",
    frequency: "توزيع التكرارات",
    diversity: "بطارية التنوع",
    ngrams: "المتتابعات (ترتيب القراءة)",
    dispersion: "الانتشار",
    keyness: "اللفتانية (مقابل مجموعة مرجعية)",
    kwic: "الحواشي السياقية البصرية",
    run: "تشغيل",
    evidence: "الدليل",
    ungroundedFlag: "غير مسند",
  },
  assistant: {
    placeholder: "اسأل عن مجموعة الصور… مثل: «قارن الأنماط التكوينية بين الحملتين»",
    ask: "اسأل",
    grounded: "مسند",
    toolsUsed: "الأدوات المستخدمة",
    disclaimer:
      "كلُّ دعوى تُسند إلى استدعاء أداة أدناه أو تُعلَّم بأنها غير مسندة. الدعاوى التفسيرية فرضيات مؤطَّرة نظريًا.",
  },
  settings: {
    aiProviders: "مزودات الذكاء الاصطناعي",
    ethics: "الأخلاقيات والموافقة",
    companion: "وضع الرفيق",
    appearance: "المظهر",
    language: "اللغة",
    facial: "تحليل الوجوه والأجساد",
    facialNote:
      "اختياري ومعطَّل افتراضيًا. إشارات وصفية فقط — لا تعرُّف هويات أبدًا. لا تُستخرج إحداثيات GPS مطلقًا.",
    companionNote:
      "تكامل اختياري موثَّق مع محرك كوربس مايند (نصوص) عبر HTTP. ليس مطلوبًا لأي ميزة في لِنس.",
    cloud: "الذكاء الاصطناعي السحابي",
    cloudNote: "معطَّل افتراضيًا. عند تفعيله يظهر مؤشّر دائم.",
    theme: "السمة",
  },
};

export const STRINGS: Record<Lang, typeof en> = { en, ar };

export function isRTL(lang: Lang): boolean {
  return lang === "ar";
}
