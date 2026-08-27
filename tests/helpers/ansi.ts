const ESCAPE = 0x1b;

/** Removes SGR escape sequences, so styled output can be compared as text. */
export function stripAnsi(text: string): string {
  let result = "";
  let index = 0;
  while (index < text.length) {
    if (text.charCodeAt(index) === ESCAPE && text[index + 1] === "[") {
      const end = text.indexOf("m", index);
      if (end !== -1) {
        index = end + 1;
        continue;
      }
    }
    result += text[index];
    index += 1;
  }
  return result;
}
