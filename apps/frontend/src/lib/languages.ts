/** Ngôn ngữ Whisper / faster-whisper hỗ trợ (+ auto detect). */
export type LanguageOption = { id: string; label: string }

/** Ưu tiên các ngôn ngữ hay dùng lên đầu. */
const PRIORITY = ['auto', 'vi', 'en', 'zh', 'yue', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'th', 'id', 'ms', 'ru']

const LABELS: Record<string, string> = {
  auto: 'Tự nhận diện (auto)',
  af: 'Afrikaans',
  am: 'Amharic',
  ar: 'Arabic',
  as: 'Assamese',
  az: 'Azerbaijani',
  ba: 'Bashkir',
  be: 'Belarusian',
  bg: 'Bulgarian',
  bn: 'Bengali',
  bo: 'Tibetan',
  br: 'Breton',
  bs: 'Bosnian',
  ca: 'Catalan',
  cs: 'Czech',
  cy: 'Welsh',
  da: 'Danish',
  de: 'German',
  el: 'Greek',
  en: 'English',
  es: 'Spanish',
  et: 'Estonian',
  eu: 'Basque',
  fa: 'Persian',
  fi: 'Finnish',
  fo: 'Faroese',
  fr: 'French',
  gl: 'Galician',
  gu: 'Gujarati',
  ha: 'Hausa',
  haw: 'Hawaiian',
  he: 'Hebrew',
  hi: 'Hindi',
  hr: 'Croatian',
  ht: 'Haitian Creole',
  hu: 'Hungarian',
  hy: 'Armenian',
  id: 'Indonesian',
  is: 'Icelandic',
  it: 'Italian',
  ja: 'Japanese',
  jw: 'Javanese',
  ka: 'Georgian',
  kk: 'Kazakh',
  km: 'Khmer',
  kn: 'Kannada',
  ko: 'Korean',
  la: 'Latin',
  lb: 'Luxembourgish',
  ln: 'Lingala',
  lo: 'Lao',
  lt: 'Lithuanian',
  lv: 'Latvian',
  mg: 'Malagasy',
  mi: 'Maori',
  mk: 'Macedonian',
  ml: 'Malayalam',
  mn: 'Mongolian',
  mr: 'Marathi',
  ms: 'Malay',
  mt: 'Maltese',
  my: 'Myanmar',
  ne: 'Nepali',
  nl: 'Dutch',
  nn: 'Norwegian Nynorsk',
  no: 'Norwegian',
  oc: 'Occitan',
  pa: 'Punjabi',
  pl: 'Polish',
  ps: 'Pashto',
  pt: 'Portuguese',
  ro: 'Romanian',
  ru: 'Russian',
  sa: 'Sanskrit',
  sd: 'Sindhi',
  si: 'Sinhala',
  sk: 'Slovak',
  sl: 'Slovenian',
  sn: 'Shona',
  so: 'Somali',
  sq: 'Albanian',
  sr: 'Serbian',
  su: 'Sundanese',
  sv: 'Swedish',
  sw: 'Swahili',
  ta: 'Tamil',
  te: 'Telugu',
  tg: 'Tajik',
  th: 'Thai',
  tk: 'Turkmen',
  tl: 'Tagalog',
  tr: 'Turkish',
  tt: 'Tatar',
  uk: 'Ukrainian',
  ur: 'Urdu',
  uz: 'Uzbek',
  vi: 'Tiếng Việt',
  yi: 'Yiddish',
  yo: 'Yoruba',
  zh: 'Chinese (Mandarin)',
  yue: 'Chinese (Cantonese)',
}

/** Codes từ faster-whisper tokenizer. */
export const WHISPER_LANGUAGE_CODES = [
  'af', 'am', 'ar', 'as', 'az', 'ba', 'be', 'bg', 'bn', 'bo', 'br', 'bs', 'ca', 'cs',
  'cy', 'da', 'de', 'el', 'en', 'es', 'et', 'eu', 'fa', 'fi', 'fo', 'fr', 'gl', 'gu',
  'ha', 'haw', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw', 'ka',
  'kk', 'km', 'kn', 'ko', 'la', 'lb', 'ln', 'lo', 'lt', 'lv', 'mg', 'mi', 'mk', 'ml',
  'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'nn', 'no', 'oc', 'pa', 'pl', 'ps', 'pt',
  'ro', 'ru', 'sa', 'sd', 'si', 'sk', 'sl', 'sn', 'so', 'sq', 'sr', 'su', 'sv', 'sw',
  'ta', 'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'uk', 'ur', 'uz', 'vi', 'yi', 'yo',
  'zh', 'yue',
] as const

function labelFor(code: string): string {
  return LABELS[code] || code.toUpperCase()
}

export const LANGUAGE_OPTIONS: LanguageOption[] = [
  { id: 'auto', label: labelFor('auto') },
  ...[...WHISPER_LANGUAGE_CODES]
    .sort((a, b) => {
      const ia = PRIORITY.indexOf(a)
      const ib = PRIORITY.indexOf(b)
      if (ia !== -1 || ib !== -1) {
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
      }
      return labelFor(a).localeCompare(labelFor(b), 'vi')
    })
    .map((id) => ({ id, label: `${labelFor(id)} (${id})` })),
]

/** `auto` → undefined để Whisper tự detect. */
export function languageForApi(selected: string): string | undefined {
  if (!selected || selected === 'auto') return undefined
  return selected
}
