export type SearchParams = Record<string, string | string[] | undefined>;

export function firstParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

export function flashMessages(params: SearchParams): { notice?: string; error?: string } {
  return {
    notice: firstParam(params.notice),
    error: firstParam(params.error),
  };
}
