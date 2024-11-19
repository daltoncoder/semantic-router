import { LitNodeClient } from "@lit-protocol/lit-node-client";
import {
  createSiweMessage,
  generateAuthSig,
  LitAbility,
  LitAccessControlConditionResource,
} from "@lit-protocol/auth-helpers";
import { LIT_RPC, LitNetwork } from "@lit-protocol/constants";
import { ethers } from "ethers";

import { promises as fs } from "fs";


export const runExample = async (base64Params) => {
  // Check if base64Params is provided, otherwise fallback to process.env.ROUTER_CONFIG
  const base64String = base64Params || process.env.ROUTER_CONFIG;
  
  if (!base64String) {
    throw new Error('No configuration provided: ROUTER_CONFIG environment variable or base64Params parameter is required');
  }

  // Decode base64 parameters
  const params = JSON.parse(Buffer.from(base64String, 'base64').toString());
  const { accessControlConditions, ciphertext, dataToEncryptHash, hostPrivateKey } = params;

  const litNodeClient = new LitNodeClient({
    litNetwork: LitNetwork.DatilDev,
    debug: false,
  });
  await litNodeClient.connect();

  try {
    const ethersSigner = new ethers.Wallet(
      hostPrivateKey,
      new ethers.providers.JsonRpcProvider(LIT_RPC.CHRONICLE_YELLOWSTONE)
    );

    const sessionSignatures = await litNodeClient.getSessionSigs({
      chain: "ethereum",
      expiration: new Date(Date.now() + 1000 * 60 * 10).toISOString(), // 10 minutes
      resourceAbilityRequests: [
        {
          resource: new LitAccessControlConditionResource("*"),
          ability: LitAbility.AccessControlConditionDecryption,
        },
      ],
      authNeededCallback: async ({ uri, expiration, resourceAbilityRequests }) => {
        const toSign = await createSiweMessage({
          uri,
          expiration,
          resources: resourceAbilityRequests,
          walletAddress: await ethersSigner.getAddress(),
          nonce: await litNodeClient.getLatestBlockhash(),
          litNodeClient,
        });

        return await generateAuthSig({
          signer: ethersSigner,
          toSign,
        });
      },
    });

    const decryptionResponse = await litNodeClient.decrypt({
      chain: "ethereum",
      sessionSigs: sessionSignatures,
      ciphertext,
      dataToEncryptHash,
      accessControlConditions,
    });

    const decryptedString = new TextDecoder().decode(
      decryptionResponse.decryptedData,
    );
    
    // Parse the decrypted JSON string
    const config = JSON.parse(decryptedString);
    
    // Create config directory if it doesn't exist
    await fs.mkdir('config', { recursive: true });
    
    // Write individual config files
    try {
      await fs.writeFile('config/google.json', JSON.stringify(config.google, null, 2));
      await fs.writeFile('config/opengradient.json', JSON.stringify(config.opengradient, null, 2));
      await fs.writeFile('config/index.json', JSON.stringify(config.index, null, 2));
      await fs.writeFile('config/project.json', JSON.stringify(config.project, null, 2));
      
      console.log('✅ Config files written successfully');
      return config;
    } catch (writeError) {
      console.error('❌ Error writing config files:', writeError);
      throw writeError;
    }

  } catch (error) {
    console.error('❌ Decryption error:', error);
    throw error;
  } finally {
    litNodeClient.disconnect();
  }
};


runExample()