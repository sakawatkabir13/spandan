export function errorMessage(error: any, fallback = 'Unable to complete this request. Please try again.'): string {
  if (!error?.response) {
    return error?.code === 'ECONNABORTED'
      ? 'The request took too long. Please check your connection and retry.'
      : 'Unable to reach Spandan. Check your internet connection and try again.';
  }
  const details = error.response.data?.error?.details;
  if (Array.isArray(details) && details.length) {
    return details.map((detail: any) => {
      const field = detail.loc?.filter((x: string) => x !== 'body').join(' ').replaceAll('_', ' ');
      return [field, detail.msg?.replace(/^Value error, /, '')].filter(Boolean).join(': ');
    }).join('; ');
  }
  return error.response.data?.error?.message || fallback;
}
