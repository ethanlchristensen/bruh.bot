import type {
  DefaultOptions,
  UseMutationOptions,
  UseQueryOptions,
} from '@tanstack/react-query';

export const queryConfig = {
  queries: {
    // throwOnError: true,
    refetchOnWindowFocus: false,
    retry: false,
    staleTime: 1000 * 60,
  },
} satisfies DefaultOptions;

export type ApiFnReturnType<TFnType extends (...args: any) => Promise<any>> =
  Awaited<ReturnType<TFnType>>;

export type QueryConfig<T extends (...args: Array<any>) => Promise<any>> = Omit<
  UseQueryOptions<ApiFnReturnType<T>, Error, ApiFnReturnType<T>, any>,
  'queryKey' | 'queryFn'
>;

export type MutationConfig<
  TMutationFnType extends (...args: any) => Promise<any>,
> = UseMutationOptions<
  ApiFnReturnType<TMutationFnType>,
  Error,
  Parameters<TMutationFnType>[0]
>;
