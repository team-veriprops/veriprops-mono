/**
 * Renders a JSON-LD structured-data block. Use with the builders in `@lib/seo`
 * (organizationJsonLd, faqJsonLd, legalDocumentJsonLd, …). Server-safe; emits a
 * single <script type="application/ld+json"> tag.
 */
export default function JsonLd({ data }: { data: object | object[] }) {
  const payload = Array.isArray(data) ? data : [data];
  return (
    <>
      {payload.map((item, i) => (
        <script
          key={i}
          type="application/ld+json"
          // Schema content is built server-side from trusted sources only.
          dangerouslySetInnerHTML={{ __html: JSON.stringify(item) }}
        />
      ))}
    </>
  );
}
