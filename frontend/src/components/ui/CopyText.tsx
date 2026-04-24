import { copyToClipboard } from "@lib/utils";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import ToolTipComponent from "./ToolTipComponent";

interface CopyTextProps {
  text: string;
}

export function CopyText({ text }: CopyTextProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyToClipboard(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      onClick={handleCopy}
      className="flex items-center gap-2 cursor-pointer px-2 py-1 rounded hover:bg-muted transition select-none text-sm text-muted-foreground mt-1 font-mono"
    >
      <span className="font-mono">{text}</span>
      <ToolTipComponent label="Copy value">
      {copied ? (
        <Check className="h-4 w-4 text-green-500" />
      ) : (
        <Copy className="h-4 w-4 text-muted-foreground" />
      )}
      </ToolTipComponent>
    </div>
  );
}