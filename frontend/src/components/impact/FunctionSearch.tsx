// components/impact/FunctionSearch.tsx  —  CodeoMentis Week 3
//
// Searchable combobox for selecting a function to analyse.
// Uses shadcn/ui Popover + Command components.
// Debounced input → hits /api/impact/{repoId}/functions?search=...

import { useState, useEffect } from "react";
import { Check, ChevronsUpDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useFunctionList, type FunctionOption } from "@/hooks/useImpact";

interface Props {
  repoId: string;
  value: string | null;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export default function FunctionSearch({ repoId, value, onChange, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce search input by 300ms
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data: functions = [], isLoading } = useFunctionList(repoId, debouncedSearch);

  const selectedFn = functions.find((f) => f.id === value);
  const displayLabel = selectedFn
    ? `${selectedFn.function_name}  (${selectedFn.file_path})`
    : value ?? "Select a function…";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn(
            "w-full justify-between font-mono text-sm truncate",
            "bg-slate-900 border-slate-700 text-slate-100",
            "hover:bg-slate-800 hover:border-slate-600"
          )}
        >
          <span className="truncate">{displayLabel}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-[520px] p-0 bg-slate-900 border-slate-700"
        align="start"
      >
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search function name…"
            value={search}
            onValueChange={setSearch}
            className="text-slate-100"
          />
          <CommandList>
            {isLoading && (
              <div className="flex items-center gap-2 p-3 text-sm text-slate-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                Searching…
              </div>
            )}
            {!isLoading && functions.length === 0 && (
              <CommandEmpty className="text-slate-400">No functions found.</CommandEmpty>
            )}
            <CommandGroup>
              {functions.map((fn: FunctionOption) => (
                <CommandItem
                  key={fn.id}
                  value={fn.id}
                  onSelect={() => {
                    onChange(fn.id);
                    setOpen(false);
                  }}
                  className="text-slate-200 data-[selected=true]:bg-slate-800"
                >
                  <Check
                    className={cn(
                      "mr-2 h-3.5 w-3.5 text-teal-400",
                      value === fn.id ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <span className="font-mono font-medium text-teal-300 mr-2">
                    {fn.function_name}
                  </span>
                  <span className="text-xs text-slate-500 truncate">{fn.file_path}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}