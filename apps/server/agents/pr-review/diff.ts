export const MAX_DIFF_BYTES = 100_000;
export const MAX_FILE_BYTES = 20_000;

const GENERATED_PATHS = [
  /(^|\/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock|Cargo\.lock|Gemfile\.lock|composer\.lock|go\.sum)$/,
  /(^|\/)(dist|build|out|vendor|node_modules|coverage)\//,
  /\.min\.(js|css|map)$/,
  /\.(js|css)\.map$/,
];

const BINARY_PATHS =
  /\.(png|jpe?g|gif|bmp|ico|webp|pdf|zip|gz|tgz|bz2|xz|7z|jar|so|dylib|dll|exe|wasm|woff2?|ttf|otf|eot|mp3|mp4|mov|avi)$/i;

const FILE_HEADER = /^diff --git (?:"?a\/(.+?)"? )?"?b\/(.+?)"?$/;

export interface SkippedFile {
  readonly path: string;
  readonly reason: string;
}

export interface FilteredDiff {
  readonly text: string;
  readonly skipped: readonly SkippedFile[];
  readonly includedFiles: number;
  readonly originalBytes: number;
  readonly bytes: number;
}

interface FileDiff {
  readonly path: string;
  readonly text: string;
}

export function splitDiff(diff: string): FileDiff[] {
  const files: FileDiff[] = [];
  let path = "";
  let lines: string[] = [];

  const flush = () => {
    const text = lines.join("\n").trim();
    if (text !== "") {
      files.push({ path, text: `${text}\n` });
    }
  };

  for (const line of diff.split("\n")) {
    const header = FILE_HEADER.exec(line);
    if (header) {
      flush();
      path = header[2] ?? header[1] ?? "";
      lines = [line];
      continue;
    }
    lines.push(line);
  }
  flush();
  return files;
}

function skipReason(file: FileDiff): string | undefined {
  if (GENERATED_PATHS.some((pattern) => pattern.test(file.path))) {
    return "generated or vendored";
  }
  if (BINARY_PATHS.test(file.path) || file.text.includes("GIT binary patch")) {
    return "binary";
  }
  if (/^Binary files .* differ$/m.test(file.text)) {
    return "binary";
  }
  if (file.text.length > MAX_FILE_BYTES) {
    return `larger than ${MAX_FILE_BYTES} bytes`;
  }
  return undefined;
}

export function filterDiff(
  diff: string,
  maxBytes: number = MAX_DIFF_BYTES,
): FilteredDiff {
  const skipped: SkippedFile[] = [];
  const kept: string[] = [];
  let bytes = 0;

  for (const file of splitDiff(diff)) {
    const reason = skipReason(file);
    if (reason !== undefined) {
      skipped.push({ path: file.path, reason });
      continue;
    }
    if (bytes + file.text.length > maxBytes) {
      skipped.push({ path: file.path, reason: "diff size budget exhausted" });
      continue;
    }
    kept.push(file.text);
    bytes += file.text.length;
  }

  return {
    text: kept.join(""),
    skipped,
    includedFiles: kept.length,
    originalBytes: diff.length,
    bytes,
  };
}

export function renderOmissions(skipped: readonly SkippedFile[]): string {
  if (skipped.length === 0) {
    return "";
  }
  const listed = skipped.map((each) => `- ${each.path} (${each.reason})`).join("\n");
  return (
    `\n[angel] ${skipped.length} file(s) omitted from this diff — ` +
    `review only what is shown above and do not assume anything about them:\n${listed}\n`
  );
}
