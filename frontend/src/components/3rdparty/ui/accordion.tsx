"use client"

import * as React from "react"
import * as AccordionPrimitive from "@radix-ui/react-accordion"
import { ChevronDownIcon, MinusIcon, PlusIcon } from "lucide-react"

import { cn } from "@lib/utils"

function Accordion({
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Root>) {
  return <AccordionPrimitive.Root data-slot="accordion" {...props} />
}

function AccordionItem({
  className,
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Item>) {
  return (
    <AccordionPrimitive.Item
      data-slot="accordion-item"
      className={cn("border-b last:border-b-0", className)}
      {...props}
    />
  )
}

/**
 * `chevron` rotates a single down-arrow when open; `plus-minus` swaps a + for a − (the
 * editorial FAQ style). Both are decorative — Radix exposes the state via `aria-expanded`.
 */
type AccordionIndicator = "chevron" | "plus-minus"

const indicatorIconClass = "pointer-events-none size-4 shrink-0"

function AccordionTrigger({
  className,
  children,
  indicator = "chevron",
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Trigger> & {
  indicator?: AccordionIndicator
}) {
  return (
    <AccordionPrimitive.Header className="flex">
      <AccordionPrimitive.Trigger
        data-slot="accordion-trigger"
        className={cn(
          "group focus-visible:border-ring focus-visible:ring-ring/50 flex flex-1 items-start justify-between gap-4 rounded-md py-4 text-left text-sm font-medium transition-all outline-none hover:underline focus-visible:ring-[3px] disabled:pointer-events-none disabled:opacity-50",
          indicator === "chevron" && "[&[data-state=open]>svg]:rotate-180",
          className
        )}
        {...props}
      >
        {children}
        {indicator === "chevron" ? (
          <ChevronDownIcon className={cn(indicatorIconClass, "text-muted-foreground translate-y-0.5 transition-transform duration-200")} />
        ) : (
          <>
            <PlusIcon aria-hidden className={cn(indicatorIconClass, "group-data-[state=open]:hidden")} />
            <MinusIcon aria-hidden className={cn(indicatorIconClass, "hidden group-data-[state=open]:block")} />
          </>
        )}
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  )
}

function AccordionContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof AccordionPrimitive.Content>) {
  return (
    <AccordionPrimitive.Content
      data-slot="accordion-content"
      className="data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down overflow-hidden text-sm"
      {...props}
    >
      <div className={cn("pt-0 pb-4", className)}>{children}</div>
    </AccordionPrimitive.Content>
  )
}

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
