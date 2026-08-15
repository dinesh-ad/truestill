/**
 * `cn` - the class merger every shadcn component imports.
 *
 * `clsx` resolves conditionals; `twMerge` resolves CONFLICTS, which is the half that matters:
 * `cn("p-2", "p-4")` is `p-4` rather than both, so a component's default padding can be
 * overridden by a caller without specificity games or `!important`.
 *
 * Written here rather than pulled by `shadcn init`, because init writes into whatever CSS file
 * `components.json` names and this project's CSS is hand-owned.
 */
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
