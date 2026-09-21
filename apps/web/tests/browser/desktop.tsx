import React from 'react';
import {createRoot} from 'react-dom/client';
import {setAuthToken} from '../../src/shared/api/client';
import {InvFileExplorer} from '../../src/features/desktop/InvFileExplorer';
import {ModelStudioView} from '../../src/features/desktop/ModelStudioView';
import {ResourceExplorer} from '../../src/features/desktop/ResourceExplorer';

const root = createRoot(document.getElementById('root')!);
let generation = 0;

export type DesktopBrowserView = 'files' | 'model' | 'fabric' | 'resource';

(window as any).mountDesktopTest = (input: {
  token: string;
  projectId: string;
  view: DesktopBrowserView;
  initialTab?: 'overview' | 'storage' | 'pools' | 'nodes' | 'discovery';
}) => {
  setAuthToken(input.token);
  if (input.view === 'files') {
    root.render(<InvFileExplorer key={++generation} />);
  } else if (input.view === 'model') {
    root.render(<ModelStudioView key={++generation} projectId={input.projectId} />);
  } else if (input.view === 'fabric' || input.view === 'resource') {
    root.render(
      <ResourceExplorer
        key={++generation}
        nodes={[]}
        initialTab={input.initialTab || 'discovery'}
      />
    );
  }
};

