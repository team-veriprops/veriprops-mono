/**
 * Serialize a JSON-LD object for safe embedding inside a <script> tag.
 * `JSON.stringify` does not escape `<`/`>`/`&`, so a `</script>` sequence in any
 * string value (e.g. a user-supplied title/description flowing into a builder) could
 * break out of the script element. Escape those characters via unicode sequences,
 * which stay valid JSON while defeating the breakout.
 */
function serializeJsonLd(item: object): string {
  return JSON.stringify(item)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026");
}

/** Renders one or more JSON-LD blocks. Pair with the builders in `@lib/seo`. */
export default function JsonLd({ data }: { data: object | object[] }) {
  const payload = Array.isArray(data) ? data : [data];
  return (
    <>
      {payload.map((item, i) => (
        <script
          key={i}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(item) }}
        />
      ))}
    </>
  );
}
