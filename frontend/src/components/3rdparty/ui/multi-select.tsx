"use client";

import * as React from "react";
import { Command, CommandGroup, CommandInput, CommandItem } from "@3rdparty/ui/command";
import { Badge } from "@3rdparty/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@3rdparty/ui/popover";
import { Button } from "@3rdparty/ui/button";
import { Check, ChevronsUpDown, X } from "lucide-react";

interface MultiSelectProps<T extends string> {
  options: T[];
  value: T[];
  onChange: (value: T[]) => void;
  placeholder?: string;
}

export function MultiSelect<T extends string>({
  options,
  value,
  onChange,
  placeholder = "Select options...",
}: MultiSelectProps<T>) {
  const [open, setOpen] = React.useState(false);

  const toggleOption = (option: T) => {
    if (value.includes(option)) {
      onChange(value.filter((v) => v !== option));
    } else {
      onChange([...value, option]);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
        >
          <div className="flex flex-wrap gap-1">
            {value.length === 0 && (
              <span className="text-muted-foreground">{placeholder}</span>
            )}
            {value.map((v) => (
              <Badge
                key={v}
                variant="secondary"
                className="px-2 py-0 text-xs flex items-center gap-1"
              >
                {v}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleOption(v);
                  }}
                />
              </Badge>
            ))}
          </div>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0 w-[220px]">
        <Command>
          <CommandInput placeholder="Search..." />
          <CommandGroup>
            {options.map((option) => (
              <CommandItem
                key={option}
                onSelect={() => toggleOption(option)}
                className="flex items-center justify-between"
              >
                {option}
                {value.includes(option) && (
                  <Check className="h-4 w-4 text-primary" />
                )}
              </CommandItem>
            ))}
          </CommandGroup>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
