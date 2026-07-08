interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function SearchInput({ value, onChange, placeholder }: SearchInputProps) {
  return (
    <div className="relative">
      <i className="fa-solid fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-[#1a1f2e] border border-white/10 rounded-lg pl-9 pr-4 py-2 text-white text-sm placeholder:text-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
      />
    </div>
  );
}
