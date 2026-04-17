export function truncate(text: string, maxLength: number, ellipsis = "..."): string {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength - ellipsis.length) + ellipsis;
}

export function truncateWords(text: string, maxLength: number, ellipsis = "..."): string {
    if (text.length <= maxLength) return text;
    const truncated = text.slice(0, maxLength - ellipsis.length);
    const lastSpace = truncated.lastIndexOf(" ");
    return (lastSpace > 0 ? truncated.slice(0, lastSpace) : truncated) + ellipsis;
}

export function truncateByWordCount(text: string, maxWords: number, ellipsis = "..."): string {
    const words = text.trim().split(/\s+/);
    if (words.length <= maxWords) return text;
    return words.slice(0, maxWords).join(" ") + ellipsis;
}

export function truncateByLineCount(text: string, maxLines: number, ellipsis = "..."): string {
    const lines = text.split("\n");
    if (lines.length <= maxLines) return text;
    return lines.slice(0, maxLines).join("\n") + ellipsis;
}

export function truncateMiddle(text: string, maxLength: number, ellipsis = "..."): string {
    if (text.length <= maxLength) return text;
    const charsToShow = maxLength - ellipsis.length;
    const frontChars = Math.ceil(charsToShow / 2);
    const backChars = Math.floor(charsToShow / 2);
    return text.slice(0, frontChars) + ellipsis + text.slice(text.length - backChars);
}

export function truncateByBytes(text: string, maxBytes: number, ellipsis = "..."): string {
    const encoder = new TextEncoder();
    if (encoder.encode(text).length <= maxBytes) return text;

    const ellipsisBytes = encoder.encode(ellipsis).length;
    let byteCount = 0;
    let charIndex = 0;

    for (const char of text) {
        const charBytes = encoder.encode(char).length;
        if (byteCount + charBytes > maxBytes - ellipsisBytes) break;
        byteCount += charBytes;
        charIndex += char.length;
    }

    return text.slice(0, charIndex) + ellipsis;
}

export function truncateHtml(html: string, maxLength: number, ellipsis = "..."): string {
    const plain = html.replace(/<[^>]*>/g, "");
    return truncateWords(plain, maxLength, ellipsis);
}

export interface TruncateOptions {
    maxLength: number;
    ellipsis?: string;
    strategy?: "end" | "words" | "middle";
}

export function smartTruncate(text: string, options: TruncateOptions): string {
    const { maxLength, ellipsis = "...", strategy = "words" } = options;

    switch (strategy) {
        case "end":    return truncate(text, maxLength, ellipsis);
        case "words":  return truncateWords(text, maxLength, ellipsis);
        case "middle": return truncateMiddle(text, maxLength, ellipsis);
        default:       return truncate(text, maxLength, ellipsis);
    }
}