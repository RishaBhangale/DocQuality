import { ShieldCheck, Building2 } from 'lucide-react';

interface SplashPageProps {
  onSelect: (mode: 'compliance' | 'banking') => void;
}

export function SplashPage({ onSelect }: SplashPageProps) {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[#F4F7FB] font-sans">
      <div className="max-w-5xl w-full">
        <div className="text-center mb-16 animate-fade-in-up">
          <div className="w-16 h-16 mx-auto bg-blue-900 rounded-2xl flex items-center justify-center shadow-lg mb-6">
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight mb-4">
            Document Intelligence Platform
          </h1>
          <p className="text-lg text-slate-500 max-w-2xl mx-auto font-medium">
            Select your specialized workspace to proceed.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {/* DocQuality Card */}
          <div
            className="rounded-3xl p-8 flex flex-col items-start relative group cursor-pointer transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_20px_25px_-5px_rgba(0,0,0,0.1),0_34px_50px_3px_rgba(0,0,0,0.08)] bg-white/95 backdrop-blur-md border border-white/20 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05),0_24px_38px_3px_rgba(0,0,0,0.06)]"
            onClick={() => onSelect('compliance')}
          >
            <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-6 border border-blue-100 group-hover:bg-blue-600 transition-colors duration-300">
              <ShieldCheck className="w-6 h-6 text-blue-600 group-hover:text-white transition-colors duration-300" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-3">AI Governance & Compliance</h2>
            <p className="text-slate-500 mb-8 flex-grow leading-relaxed">
              Evaluate unstructured documents against major universal AI standards and ensure baseline general data integrity.
            </p>
            <button className="w-full py-4 rounded-xl font-bold text-white bg-slate-900 group-hover:bg-black transition flex justify-center items-center">
              Launch Compliance Quality
            </button>
          </div>

          {/* Banking Card */}
          <div
            className="rounded-3xl p-8 flex flex-col items-start relative group cursor-pointer transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_20px_25px_-5px_rgba(0,0,0,0.1),0_34px_50px_3px_rgba(0,0,0,0.08)] bg-white/95 backdrop-blur-md border border-white/20 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05),0_24px_38px_3px_rgba(0,0,0,0.06)]"
            onClick={() => onSelect('banking')}
          >
            <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mb-6 border border-emerald-100 group-hover:bg-emerald-600 transition-colors duration-300">
              <Building2 className="w-6 h-6 text-emerald-600 group-hover:text-white transition-colors duration-300" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-3">Banking Intelligence Quality</h2>
            <p className="text-slate-500 mb-8 flex-grow leading-relaxed">
              Execute sophisticated multi-agent domain analysis enforcing strict financial regulations and generating risk insights.
            </p>
            <button className="w-full py-4 rounded-xl font-bold text-slate-900 bg-emerald-100/50 group-hover:bg-emerald-100 transition border border-emerald-200/50 flex justify-center items-center">
              Launch Banking Quality
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
