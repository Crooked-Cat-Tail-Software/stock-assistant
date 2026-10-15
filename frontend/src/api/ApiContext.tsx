import { createContext, useContext, type ReactNode } from "react";
import { api as defaultApi, type Api } from "./client";

// Components get the API client from context, so tests can supply a fake one.
const ApiContext = createContext<Api>(defaultApi);

export function ApiProvider({ api, children }: { api: Api; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): Api {
  return useContext(ApiContext);
}
