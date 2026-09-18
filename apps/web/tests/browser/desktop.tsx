import React from 'react';
import {createRoot} from 'react-dom/client';
import {setAuthToken} from '../../src/shared/api/client';
import {InvFileExplorer} from '../../src/features/desktop/InvFileExplorer';
import {ModelStudioView} from '../../src/features/desktop/ModelStudioView';
const root = createRoot(document.getElementById('root')!);
let generation = 0;
(window as any).mountDesktopTest = (input: {token: string; projectId: string; view: 'files' | 'model'}) => {
  setAuthToken(input.token);
  root.render(input.view === 'files' ? <InvFileExplorer key={++generation}/> : <ModelStudioView key={++generation} projectId={input.projectId}/>);
};
