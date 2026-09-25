"use client";

import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@components/3rdparty/ui/accordion";
import { faqs } from "./home.data";

// FAQ that answers a diaspora buyer's main objections before the final CTA. An editorial,
// ruled list: the first answer is open on arrival so the section reads as content, not a menu.
export default function FaqSection() {
  return (
    <section
      id="faq"
      className="py-20 md:py-28 bg-white"
      data-testid="faq-section"
    >
      <div className="max-w-5xl mx-auto px-6 lg:px-8">
        <div className="mb-10 md:mb-12 animate-fade-up">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4 bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            Questions, Answered
          </div>
          <h2
            className="editorial-spacing text-3xl md:text-5xl font-extrabold font-display text-brand-navy"
          >
            Everything you need to feel sure
          </h2>
          <p className="mt-4 max-w-2xl text-sm md:text-base text-brand-on-surface-variant">
            Buying from a distance is a big decision. Here&rsquo;s how we make it a safe one.
          </p>
        </div>

        <Accordion
          type="single"
          collapsible
          defaultValue="faq-0"
          className="w-full animate-fade-up stagger-1"
        >
          {faqs.map((faq, i) => (
            <AccordionItem
              key={faq.question}
              value={`faq-${i}`}
              data-testid={`faq-item-${i}`}
              className="border-b last:border-b border-brand-outline-variant/40"
            >
              <AccordionTrigger
                indicator="plus-minus"
                className="items-center py-5 md:py-6 text-base md:text-lg font-semibold text-brand-navy hover:no-underline hover:text-brand-viridian [&>svg]:text-brand-viridian"
              >
                {faq.question}
              </AccordionTrigger>
              <AccordionContent className="pb-6">
                <p className="max-w-4xl text-sm md:text-base leading-relaxed text-brand-on-surface-variant">
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
