// src/types/vis-modules.d.ts
declare module 'vis-network' {
  export interface Node {
    id: string | number;
    label?: string;
    title?: string;
    group?: string;
    color?: string | { background?: string; border?: string };
    shape?: string;
    size?: number;
    [key: string]: any;
  }

  export interface Edge {
    from: string | number;
    to: string | number;
    label?: string;
    title?: string;
    color?: string;
    arrows?: string | { to?: boolean; from?: boolean; middle?: boolean };
    dashes?: boolean | number[];
    width?: number;
    [key: string]: any;
  }

  export interface Options {
    nodes?: {
      shape?: string;
      size?: number;
      font?: {
        size?: number;
        color?: string;
        face?: string;
      };
      borderWidth?: number;
      shadow?: boolean;
      [key: string]: any;
    };
    edges?: {
      arrows?: string | { to?: boolean; from?: boolean };
      smooth?: boolean | { type?: string; roundness?: number };
      color?: string | { color?: string; highlight?: string; hover?: string };
      width?: number;
      [key: string]: any;
    };
    physics?: {
      enabled?: boolean;
      solver?: 'barnesHut' | 'repulsion' | 'hierarchicalRepulsion';
      [key: string]: any;
    };
    interaction?: {
      dragNodes?: boolean;
      dragView?: boolean;
      hover?: boolean;
      tooltipDelay?: number;
      zoomView?: boolean;
      [key: string]: any;
    };
    layout?: {
      hierarchical?: {
        enabled?: boolean;
        direction?: 'UD' | 'DU' | 'LR' | 'RL';
        sortMethod?: 'directed' | 'hubsize';
        [key: string]: any;
      };
      [key: string]: any;
    };
    [key: string]: any;
  }

  export class Network {
    constructor(container: HTMLElement, data: { nodes: DataSet; edges: DataSet }, options?: Options);
    destroy(): void;
    fit(options?: { animation?: boolean | number; [key: string]: any }): void;
    selectNodes(ids: (string | number)[], highlightEdges?: boolean): void;
    unselectAll(): void;
    redraw(): void;
    setOptions(options: Options): void;
    getBody(): any;
    getPositions(): { [key: string]: { x: number; y: number } };
    moveTo(options: { position?: { x: number; y: number }; scale?: number; offset?: { x: number; y: number }; animation?: boolean | number }): void;
    on(event: string, callback: (params: any) => void): void;
    off(event: string, callback?: (params: any) => void): void;
    [key: string]: any;
  }
}

declare module 'vis-data' {
  export class DataSet<T = any> {
    constructor(data?: T[], options?: any);
    add(data: T | T[]): (string | number)[];
    update(data: T | T[]): (string | number)[];
    remove(id: string | number | (string | number)[]): void;
    get(): T[];
    get(id: string | number): T;
    get(ids: (string | number)[]): T[];
    clear(): void;
    forEach(callback: (item: T, id: string | number) => void): void;
    map<U>(callback: (item: T, id: string | number) => U, array?: U[]): U[];
    length(): number;
    [key: string]: any;
  }
}
