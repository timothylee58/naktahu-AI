'use client';

import { useId, useState, type KeyboardEvent, type RefObject } from 'react';
import { Input } from '@/components/ui/input';
import { fill, normName, stepIndex, type Place } from '@/lib/warung-watch/crowd';

interface PlaceSearchProps {
  query: string;
  onQueryChange: (value: string) => void;
  suggestions: Place[];
  onPick: (place: Place) => void;
  onAddNew: (name: string) => void;
  hint?: string;
  inputRef: RefObject<HTMLInputElement | null>;
  t: (key: string) => string;
}

type Option = { id: string; kind: 'place'; place: Place } | { id: string; kind: 'add'; name: string };

// ARIA 1.2 combobox with a listbox popup: the input keeps focus, arrows move
// aria-activedescendant, Enter picks, Escape closes.
export function PlaceSearch({ query, onQueryChange, suggestions, onPick, onAddNew, hint, inputRef, t }: PlaceSearchProps) {
  const uid = useId();
  const listId = `${uid}-list`;
  const [active, setActive] = useState(-1);
  const [dismissed, setDismissed] = useState(false);

  const trimmed = query.trim();
  const canAdd = trimmed.length >= 2 && !suggestions.some((place) => normName(place.name) === normName(query));
  const options: Option[] = [
    ...suggestions.map((place): Option => ({ id: `${uid}-opt-${place.key}`, kind: 'place', place })),
    ...(canAdd ? [{ id: `${uid}-opt-add`, kind: 'add', name: trimmed } satisfies Option] : []),
  ];
  const open = !dismissed && options.length > 0;
  const activeId = open && active >= 0 && active < options.length ? options[active].id : undefined;

  const choose = (option: Option) => {
    if (option.kind === 'place') onPick(option.place);
    else onAddNew(option.name);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setDismissed(false);
      setActive((current) => stepIndex(current, event.key === 'ArrowDown' ? 1 : -1, options.length));
    } else if (event.key === 'Enter' && activeId) {
      event.preventDefault();
      choose(options[active]);
    } else if (event.key === 'Escape' && open) {
      event.preventDefault();
      setDismissed(true);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={`${uid}-input`} className="text-xs font-semibold uppercase tracking-wide text-nk-muted-aa">
        {t('warung_watch.search_label')}
      </label>
      <Input
        id={`${uid}-input`}
        ref={inputRef}
        value={query}
        onChange={(event) => {
          onQueryChange(event.target.value);
          setActive(-1);
          setDismissed(false);
        }}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        autoComplete="off"
        enterKeyHint="search"
        placeholder={t('warung_watch.search_placeholder')}
        className="h-12 text-base focus-visible:ring-2 focus-visible:ring-nk-official sm:text-sm"
      />
      {hint && <p className="text-xs text-nk-muted-aa">{hint}</p>}
      <ul
        id={listId}
        role="listbox"
        aria-label={t('warung_watch.search_results')}
        className={open ? 'flex flex-col gap-1' : 'hidden'}
      >
        {options.map((option, index) => (
          <li
            key={option.id}
            id={option.id}
            role="option"
            aria-selected={index === active}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => choose(option)}
            className={`min-h-11 cursor-pointer rounded-lg px-3 py-2 text-sm hover:bg-[var(--nk-badge-bg)] ${index === active ? 'bg-[var(--nk-badge-bg)] ring-2 ring-nk-official' : ''}`}
          >
            {option.kind === 'place' ? (
              <>
                <span className="text-nk-ink">{option.place.name}</span>
                {option.place.location && <span className="block text-xs text-nk-muted-aa">{option.place.location}</span>}
              </>
            ) : (
              <span className="font-semibold text-nk-official-text">{fill(t('warung_watch.add_place'), { name: option.name })}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
