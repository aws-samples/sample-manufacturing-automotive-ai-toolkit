import Editor from "@monaco-editor/react";

interface Props {
  value: string;
  onChange: (val: string) => void;
  readOnly?: boolean;
  height?: string;
}

export default function MonacoJsonEditor({
  value,
  onChange,
  readOnly = false,
  height = "500px",
}: Props) {
  return (
    <div className="h-full rounded overflow-hidden border border-[#2a3044]">
      <Editor
        height={height}
        language="json"
        theme="vs-dark"
        value={value}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "off",
          tabSize: 2,
        }}
        onChange={(v) => onChange(v ?? "")}
      />
    </div>
  );
}