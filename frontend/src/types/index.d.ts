export interface IProvider {
  id: string
  name: string
  logo: string
  type: string
  apiKey: string
  baseUrl: string
  enabled: number
}
export interface IResponse<T> {
  code: number
  data:T
  msg: string
}