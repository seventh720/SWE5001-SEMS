// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {MemoryRouter,Route,Routes,useLocation} from 'react-router-dom';
import {ProtectedRoute} from './ProtectedRoute';
const auth=vi.hoisted(()=>({user:null as null|{id:string}}));
vi.mock('../features/auth/AuthContext',()=>({useAuth:()=>auth}));
afterEach(()=>{cleanup();auth.user=null});
function Login(){const location=useLocation();const from=location.state?.from;return <p>Sign in to return to {from?.pathname}{from?.search}{from?.hash}</p>}
function mount(){render(<MemoryRouter initialEntries={['/private?event=one#ticket']}><Routes><Route element={<ProtectedRoute/>}><Route path='/private' element={<p>Private content</p>}/></Route><Route path='/login' element={<Login/>}/></Routes></MemoryRouter>)}
it('redirects signed-out visitors without exposing protected content and preserves the full return address',async()=>{mount();await screen.findByText('Sign in to return to /private?event=one#ticket');expect(screen.queryByText('Private content')).toBeNull()});
it('renders the protected page for a signed-in user',()=>{auth.user={id:'user'};mount();expect(screen.getByText('Private content')).toBeTruthy();expect(screen.queryByText(/Sign in/)).toBeNull()});
