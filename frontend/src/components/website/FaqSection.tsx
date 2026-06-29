"use client";

import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@components/3rdparty/ui/accordion";
import { faqs } from "./home.data";

// FAQ that answers a diaspora buyer's main objections before the final CTA.
export default function FaqSection() {
  return (
    <section
      id="faq"
      className="py-20 md:py-28"
      style={{ backgroundColor: "var(--brand-surface-low)" }}
      data-testid="faq-section"
    >
      <div className="max-w-3xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-12">
          <p
            className="text-xs font-bold uppercase tracking-widest mb-3"
            style={{ color: "var(--brand-viridian)" }}
          >
            Questions, Answered
          </p>
          <h2
            className="editorial-spacing text-3xl md:text-4xl font-bold"
            style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display)" }}
          >
            Everything you need to feel sure
          </h2>
          <p className="mt-4 text-sm md:text-base" style={{ color: "var(--brand-on-surface-variant)" }}>
            Buying from a distance is a big decision. Here&rsquo;s how we make it a safe one.
          </p>
        </div>

        <Accordion type="single" collapsible className="w-full">
          {faqs.map((faq, i) => (
            <AccordionItem
              key={faq.question}
              value={`faq-${i}`}
              data-testid={`faq-item-${i}`}
              style={{ borderBottom: "1px solid rgba(196,198,207,0.3)" }}
            >
              <AccordionTrigger
                className="text-base md:text-lg font-semibold"
                style={{ color: "var(--brand-navy)" }}
              >
                {faq.question}
              </AccordionTrigger>
              <AccordionContent>
                <p className="text-sm leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {faq.answer}
                </p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
