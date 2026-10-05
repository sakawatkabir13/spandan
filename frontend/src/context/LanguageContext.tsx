import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

const bengali: Record<string, string> = {
  'District': 'জেলা', 'Maximum fee (৳)': 'সর্বোচ্চ ফি (৳)', 'Available on': 'যে তারিখে ডাক্তার দেখাবেন', 'Filter Results': 'ফলাফল বাছাই করুন',
  'View Chambers & Book': 'চেম্বার দেখুন ও বুক করুন', 'My Appointments & Live Serials': 'আমার অ্যাপয়েন্টমেন্ট ও লাইভ সিরিয়াল', 'Refresh Serials': 'সিরিয়াল হালনাগাদ করুন',
  'Book Serial': 'সিরিয়াল বুক করুন', 'Confirm & Get Serial Number': 'নিশ্চিত করে সিরিয়াল নিন', 'Booking Confirmed!': 'বুকিং নিশ্চিত হয়েছে!',
  'Confirm attendance': 'উপস্থিতি নিশ্চিত করুন', 'Cancel Serial': 'সিরিয়াল বাতিল করুন', 'Yes, Cancel Serial': 'হ্যাঁ, সিরিয়াল বাতিল করুন', 'Keep Appointment': 'অ্যাপয়েন্টমেন্ট রাখুন',
  'Forgot your password?': 'পাসওয়ার্ড ভুলে গেছেন?', 'Sign In': 'প্রবেশ করুন', 'Signing in...': 'প্রবেশ করা হচ্ছে...',
  'Find Doctors': 'ডাক্তার খুঁজুন', 'AI Symptom Checker': 'এআই উপসর্গ যাচাই',
  'Login': 'প্রবেশ করুন', 'Register': 'নিবন্ধন করুন', 'Logout': 'সাইন আউট', 'Dashboard': 'ড্যাশবোর্ড',
  'Create your Spandan account': 'আপনার স্পন্দন অ্যাকাউন্ট তৈরি করুন',
  'Choose your account type below to get started': 'শুরু করতে অ্যাকাউন্টের ধরন বেছে নিন',
  'Patient Account': 'রোগীর অ্যাকাউন্ট', 'Doctor Practitioner': 'ডাক্তারের অ্যাকাউন্ট',
  'Full Name': 'পূর্ণ নাম', 'Email Address': 'ইমেইল ঠিকানা', 'Phone Number': 'ফোন নম্বর', 'Password': 'পাসওয়ার্ড',
  'Sign in': 'প্রবেশ করুন', 'Forgot password?': 'পাসওয়ার্ড ভুলে গেছেন?', 'Welcome back to Spandan': 'স্পন্দনে স্বাগতম',
  'Register as Patient': 'রোগী হিসেবে নিবন্ধন', 'Register as Doctor': 'ডাক্তার হিসেবে নিবন্ধন', 'Creating account...': 'অ্যাকাউন্ট তৈরি হচ্ছে...',
  'Find Verified Doctor Chambers': 'যাচাইকৃত ডাক্তারের চেম্বার খুঁজুন', 'Search': 'খুঁজুন', 'All Specializations': 'সব বিশেষজ্ঞ',
  'Previous': 'আগের', 'Next': 'পরের', 'Book Appointment': 'অ্যাপয়েন্টমেন্ট বুক করুন', 'Confirm Booking': 'বুকিং নিশ্চিত করুন',
  'Booking for': 'যার জন্য বুকিং', 'Myself': 'নিজের জন্য', 'Consultation': 'পরামর্শ', 'At the chamber': 'চেম্বারে',
  'Appointment History': 'অ্যাপয়েন্টমেন্টের ইতিহাস', 'Cancel': 'বাতিল', 'Reschedule visit': 'সময় পরিবর্তন',
  'Payment & receipt': 'পেমেন্ট ও রসিদ', 'notifications': 'বিজ্ঞপ্তি', 'security': 'নিরাপত্তা', 'privacy': 'গোপনীয়তা',
  'family': 'পরিবার', 'waitlist': 'অপেক্ষার তালিকা', 'billing': 'বিল', 'calendar': 'ক্যালেন্ডার', 'analytics': 'পরিসংখ্যান',
  'Account & Chamber Tools': 'অ্যাকাউন্ট ও চেম্বারের সরঞ্জাম', 'Family members': 'পরিবারের সদস্য', 'Add family member': 'পরিবারের সদস্য যোগ করুন',
};
const LanguageContext = createContext({ language: 'en', setLanguage: (_value: string) => {}, t: (value: string) => value });
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState(() => localStorage.getItem('spandan_language') === 'bn' ? 'bn' : 'en');
  useEffect(() => { localStorage.setItem('spandan_language', language); document.documentElement.lang = language; }, [language]);
  return <LanguageContext.Provider value={{ language, setLanguage, t: value => language === 'bn' ? (bengali[value] || value) : value }}>{children}</LanguageContext.Provider>;
}
export const useLanguage = () => useContext(LanguageContext);
