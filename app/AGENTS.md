## Frontend Development

- Always use the pointer (hand) cursor (`cursor-pointer`) on interactive elements like buttons
- The UI components are shadcn's `base-nova` style, built on Base UI rather than Radix: compose with `render={<Button />}` (there is no `asChild`), and use `onCheckedChange` / `onValueChange`.
- Talk to the API only through the generated client in `src/api/` (`npm run generate` after the API changes). Never hand-write fetch calls.
- Don't re-derive permissions in the UI: render what the API's `permissions` (or role) allows, and let the API enforce it.
- Every screen needs its loading, empty and error states (`src/components/states.tsx` in `app/`), and no button may lead to an action the API will refuse.

### Lessons (keep adding)

- oxlint's `react(set-state-in-effect)` rejects resetting dialog state in an effect. Mount the form inside the open dialog instead, so its state starts from props.
- Grids that contain `truncate` text need `grid-cols-1` on mobile, or they overflow the viewport.
- `FormControl` gives its single child the field's `id`, `aria-invalid` and `aria-describedby`, so it must wrap the `<Input>` itself. Put icons and buttons in a wrapper outside it; around a `<div>`, the label isn't tied to the input and errors aren't announced (both login pages had this).
