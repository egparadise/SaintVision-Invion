import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {afterEach, expect, it, vi} from 'vitest';
import {DesktopShell} from '../src/features/desktop/DesktopShell';
afterEach(() => {vi.unstubAllGlobals();});
const props = {projectId:'project',nodes:[],runs:[],approvals:[],workspaces:[],currentReviewerId:'user',onRefreshNodes:async()=>{},onApprove:async()=>{},onReject:async()=>{},onChangeUser:()=>{},onSwitchToPortalView:()=>{},currentTheme:'dark' as const,onToggleTheme:()=>{}};
it.each(['[null]', '[{"id":"win_my_computer","appId":"my-computer","isOpen":true}]'])('recovers malformed stored layout %s', saved => {
  vi.stubGlobal('localStorage',{getItem:()=>saved});
  expect(() => renderToStaticMarkup(<DesktopShell {...props}/>)).not.toThrow();
});

import {restoreDesktopLayout} from '../src/features/desktop/desktopLayout';
import type {DesktopWindow} from '../src/contracts/virtualFabric';
const defaults: DesktopWindow[] = [{id:'one',appId:'my-computer',title:'Trusted title',icon:'PC',isOpen:true,isMinimized:false,isMaximized:false,zIndex:10,position:{x:40,y:50},size:{width:900,height:600}}];
it.each(['invalid', '{}', '[null]', '[]', 'x'.repeat(32769)])('falls back safely for unusable storage', raw => {
  expect(restoreDesktopLayout(raw,defaults)).toEqual(defaults);
});
it('keeps application identity and parameters from code, clamps offscreen coordinates', () => {
  const saved = {...defaults[0],title:'Untrusted',params:{projectId:'other'},position:{x:1e6,y:-1},size:{width:1e6,height:1e6},zIndex:1e30};
  const result = restoreDesktopLayout(JSON.stringify([saved]),defaults,800,600)[0];
  expect(result.title).toBe('Trusted title');expect(result.params).toBeUndefined();
  expect(result.position).toEqual({x:720,y:40});expect(result.size).toEqual({width:768,height:480});expect(result.zIndex).toBe(10);
});
it.each([{appId:'settings'}, {size:{width:-1,height:20}}, {position:{x:'100',y:50}}, {isOpen:'true'}])('rejects invalid window preferences %o', patch => {
  expect(restoreDesktopLayout(JSON.stringify([{...defaults[0],...patch}]),defaults)).toEqual(defaults);
});
it('restores legitimate preferences while retaining windows absent in older storage', () => {
  const second = {...defaults[0],id:'two'};
  const result = restoreDesktopLayout(JSON.stringify([{...defaults[0],isOpen:false}]),[...defaults,second]);
  expect(result[0].isOpen).toBe(false);expect(result[1]).toEqual(second);
});
it('rejects duplicate identities and never mutates defaults', () => {
  const result = restoreDesktopLayout(JSON.stringify([defaults[0],defaults[0]]),defaults);
  result[0].position.x=999;expect(defaults[0].position.x).toBe(40);
});

it('renders mounted approval center, terminal, and settings windows when open', () => {
  const openSaved = JSON.stringify([
    { id: 'win_approvals', appId: 'approvals', isOpen: true, isMinimized: false, isMaximized: false, zIndex: 11, position: { x: 50, y: 50 }, size: { width: 800, height: 500 } },
    { id: 'win_terminal', appId: 'terminal', isOpen: true, isMinimized: false, isMaximized: false, zIndex: 12, position: { x: 100, y: 100 }, size: { width: 800, height: 500 } },
    { id: 'win_settings', appId: 'settings', isOpen: true, isMinimized: false, isMaximized: false, zIndex: 13, position: { x: 150, y: 150 }, size: { width: 800, height: 500 } },
  ]);
  vi.stubGlobal('localStorage', { getItem: () => openSaved });
  const markup = renderToStaticMarkup(
    <DesktopShell
      {...props}
      workspaces={[{ id: 'wsp_test', name: 'Workspace Test', status: 'ready' } as any]}
    />
  );
  expect(markup).toContain('거버넌스 승인 센터');
  expect(markup).toContain('Web Terminal PTY');
  expect(markup).toContain('Docker Socket 노출 여부');
});

