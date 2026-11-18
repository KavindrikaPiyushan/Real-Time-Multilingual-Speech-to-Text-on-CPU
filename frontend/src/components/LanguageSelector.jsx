const LANGUAGES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'English', label: 'English' },
  { value: 'Chinese', label: 'Mandarin Chinese' },
  { value: 'Indonesian', label: 'Bahasa Indonesia' },
]

const CHUNK_SIZES = [
  { value: 500, label: '0.5 s' },
  { value: 1000, label: '1 s' },
  { value: 2000, label: '2 s (default)' },
  { value: 5000, label: '5 s' },
]

function Select({ label, value, onChange, options, disabled }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
      {label}
      <select
        className="rounded-md border border-slate-300 bg-white px-3 py-2 font-normal disabled:bg-slate-100"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  )
}

export default function LanguageSelector({ language, onLanguage, chunkMs, onChunkMs, disabled }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Select label="Language" value={language} onChange={onLanguage} options={LANGUAGES} disabled={disabled} />
      <Select
        label="Audio chunk size" value={chunkMs} onChange={(v) => onChunkMs(Number(v))}
        options={CHUNK_SIZES} disabled={disabled}
      />
    </div>
  )
}
