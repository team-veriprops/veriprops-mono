import { PropertyDetails } from "@components/portal/verifications/add/models";

export interface SupportedPlatform {
  id: string;
  name: string;
  domain: string;
  color: string;
}

export const supportedPlatforms: SupportedPlatform[] = [
  { id: 'propertypro', name: 'PropertyPro.ng', domain: 'propertypro.ng', color: '#1E40AF' },
  { id: 'npc', name: 'Nigeria Property Centre', domain: 'nigeriapropertycentre.com', color: '#059669' },
  { id: 'jumia', name: 'Jumia House', domain: 'jumia.com.ng', color: '#EA580C' },
  { id: 'privateproperty', name: 'Private Property', domain: 'privateproperty.com.ng', color: '#DC2626' },
];

export function detectPlatform(url: string): SupportedPlatform | null {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.toLowerCase().replace('www.', '');
    
    return supportedPlatforms.find(platform => 
      hostname.includes(platform.domain.replace('www.', ''))
    ) || null;
  } catch {
    return null;
  }
}

export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

// Mock property data for different platforms
const mockPropertyData: Record<string, Partial<PropertyDetails>> = {
  propertypro: {
    propertyType: 'residential',
    propertyTitle: '4 Bedroom Semi-Detached Duplex with BQ',
    plotSize: '350',
    plotSizeUnit: 'sqm',
    address: '15 Admiralty Way, Lekki Phase 1',
    formattedAddress: '15 Admiralty Way, Lekki Phase 1, Lagos, Nigeria',
    state: 'lagos',
    lga: 'eti-osa',
    estimatedPrice: 85000000,
    currency: 'NGN',
    sourcePlatform: 'PropertyPro.ng',
  },
  npc: {
    propertyType: 'land',
    propertyTitle: 'Prime Land in Ibeju-Lekki',
    plotSize: '600',
    plotSizeUnit: 'sqm',
    address: 'Eleranigbe, Ibeju-Lekki',
    formattedAddress: 'Eleranigbe, Ibeju-Lekki, Lagos, Nigeria',
    state: 'lagos',
    lga: 'ibeju-lekki',
    estimatedPrice: 25000000,
    currency: 'NGN',
    sourcePlatform: 'Nigeria Property Centre',
  },
  jumia: {
    propertyType: 'residential',
    propertyTitle: '3 Bedroom Flat in Victoria Island',
    plotSize: '180',
    plotSizeUnit: 'sqm',
    address: 'Adeola Odeku Street, Victoria Island',
    formattedAddress: 'Adeola Odeku Street, Victoria Island, Lagos, Nigeria',
    state: 'lagos',
    lga: 'eti-osa',
    estimatedPrice: 120000000,
    currency: 'NGN',
    sourcePlatform: 'Jumia House',
  },
  privateproperty: {
    propertyType: 'commercial',
    propertyTitle: 'Office Space in Ikeja GRA',
    plotSize: '500',
    plotSizeUnit: 'sqm',
    address: 'Isaac John Street, Ikeja GRA',
    formattedAddress: 'Isaac John Street, Ikeja GRA, Lagos, Nigeria',
    state: 'lagos',
    lga: 'ikeja',
    estimatedPrice: 450000000,
    currency: 'NGN',
    sourcePlatform: 'Private Property',
  },
};

export async function extractPropertyFromUrl(url: string): Promise<Partial<PropertyDetails> | null> {
  const platform = detectPlatform(url);
  
  if (!platform) {
    return null;
  }

  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 1500));

  const baseData = mockPropertyData[platform.id];
  
  if (!baseData) {
    return null;
  }

  // Return mock data with the source URL
  return {
    ...baseData,
    sourceUrl: url,
  };
}
