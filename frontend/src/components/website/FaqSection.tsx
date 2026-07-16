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
      className="py-20 md:py-28 bg-brand-surface-low"
      data-testid="faq-section"
    >
      <div className="max-w-3xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-12 animate-fade-up">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4 bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            Questions, Answered
          </div>
          <h2
            className="editorial-spacing text-4xl md:text-5xl font-extrabold font-display text-brand-navy"
          >
            Everything you need to feel sure
          </h2>
          <p className="mt-4 text-sm md:text-base text-brand-on-surface-variant">
            Buying from a distance is a big decision. Here&rsquo;s how we make it a safe one.
          </p>
        </div>

        <Accordion type="single" collapsible className="w-full space-y-2 animate-fade-up stagger-1">
          {faqs.map((faq, i) => (
            <AccordionItem
              key={faq.question}
              value={`faq-${i}`}
              data-testid={`faq-item-${i}`}
              className="rounded-md px-4 md:px-6 border-b-0 transition-colors hover:bg-brand-surface-card data-[state=open]:bg-brand-surface-card"
            >
              <AccordionTrigger
                className="text-base md:text-lg font-semibold text-brand-navy"
              >
                {faq.question}
              </AccordionTrigger>
              <AccordionContent>
                <p className="text-sm leading-relaxed text-brand-on-surface-variant">
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
