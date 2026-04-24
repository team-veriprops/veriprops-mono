declare module 'zxcvbn' {
  interface ZXCVBNResult {
    score: 0 | 1 | 2 | 3 | 4;
    feedback: {
      warning: string;
      suggestions: string[];
    };
    crack_times_display: Record<string, string>;
    crack_times_seconds: Record<string, number>;
    sequence: unknown[];
    calc_time: number;
  }

  function zxcvbn(password: string, user_inputs?: string[]): ZXCVBNResult;

  export = zxcvbn;
}
