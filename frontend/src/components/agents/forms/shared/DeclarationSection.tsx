"use client";

interface Props {
  value: boolean;
  onChange: (v: boolean) => void;
}

export default function DeclarationSection({ value, onChange }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Declaration</h3>
      <p className="text-xs text-gray-600">
        I declare that the information provided in this report is true, accurate, and based on my
        professional assessment. I understand that providing false information may result in
        disciplinary action and removal from the Veriprops platform.
      </p>
      <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
          style={{ cursor: "pointer", marginTop: 2 }}
          className="rounded"
        />
        <span className="text-sm text-gray-700">
          I confirm the above declaration and submit this report in good faith.
          <span className="text-red-500 ml-0.5">*</span>
        </span>
      </label>
    </div>
  );
}
