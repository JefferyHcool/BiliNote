declare module 'vue' {
  interface ComponentCustomProperties {
    $app: {
      context: string
    }
  }
}

// https://stackoverflow.com/a/64189046/479957
export {}
